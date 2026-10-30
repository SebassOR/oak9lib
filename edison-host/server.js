"use strict";

var http = require("http");
var net = require("net");
var fs = require("fs");
var path = require("path");
var url = require("url");

var ROOT = __dirname;
var PUBLIC_DIR = path.join(ROOT, "public");
var HOST = process.env.HOST || "0.0.0.0";
var PORT = parseInt(process.env.PORT || "80", 10);
var ROBOT_IP = process.env.ROBOT_IP || "192.168.100.9";
var ROBOT_PORT = parseInt(process.env.ROBOT_PORT || "8080", 10);
var DEFAULT_TEMPERATURE_C = parseFloat(process.env.AMBIENT_TEMP_C || "22");
if (!isFinite(DEFAULT_TEMPERATURE_C) ||
    DEFAULT_TEMPERATURE_C < 5 || DEFAULT_TEMPERATURE_C > 40) {
  DEFAULT_TEMPERATURE_C = 22;
}
var MAX_BODY_BYTES = 8192;

var deliveryDistances = { 1: 1000, 2: 1000, 3: 2000, 4: 2000 };
var turnDirections = { 1: 1, 2: -1, 3: 1, 4: -1 };
var busyStates = ["saliendo", "esperando_cliente", "regresando", "error"];
var orders = [];
var nextOrderId = 1;
var originReference = null;
var picoTelemetry = null;
var motorWatchdog = null;
var manualControlActive = false;
var manualSession = null;
var manualFinish = null;
var manualCommandPending = false;
var motionCancelled = false;

var coffeeMenu = [
  {
    id: "Espresso",
    description: "Café intenso, corto y con mucho carácter.",
    note: "Intenso"
  },
  {
    id: "Latte",
    description: "Espresso suave con leche cremosa.",
    note: "Cremoso"
  },
  {
    id: "Capuccino",
    description: "Espresso equilibrado con espuma de leche.",
    note: "Espumoso"
  },
  {
    id: "Americano",
    description: "Espresso alargado, ligero y fácil de disfrutar frío.",
    note: "Ligero"
  }
];

function recommendationForTemperature(temperature) {
  if (temperature >= 28) {
    return {
      cafe: "Americano",
      clima: "Ambiente cálido",
      titulo: "Algo ligero para este calor",
      detalle: "Te recomendamos un Americano. También puedes pedirlo frío."
    };
  }
  if (temperature <= 17) {
    return {
      cafe: "Capuccino",
      clima: "Ambiente fresco",
      titulo: "Un momento reconfortante",
      detalle: "Te recomendamos un Capuccino caliente y espumoso."
    };
  }
  return {
    cafe: "Latte",
    clima: "Ambiente templado",
    titulo: "Un clásico para disfrutar",
    detalle: "Te recomendamos un Latte suave y cremoso."
  };
}

function menuResponse(temperature) {
  var recommendation = recommendationForTemperature(temperature);
  var menu = [];
  var i;
  for (i = 0; i < coffeeMenu.length; i += 1) {
    menu.push({
      id: coffeeMenu[i].id,
      description: coffeeMenu[i].description,
      note: coffeeMenu[i].note,
      recommended: coffeeMenu[i].id === recommendation.cafe
    });
  }
  return {
    temperatureC: temperature,
    temperatureSource: "referencia configurable; no hay sensor meteorológico conectado",
    recommendation: recommendation,
    coffees: menu
  };
}

function sendJson(response, status, value) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store"
  });
  response.end(JSON.stringify(value));
}
function sendError(response, status, message) {
  sendJson(response, status, { error: message });
}

function readJson(request, callback) {
  var body = "";
  var finished = false;

  function done(error, value) {
    if (finished) return;
    finished = true;
    callback(error, value);
  }

  request.on("data", function (chunk) {
    body += chunk;
    if (Buffer.byteLength(body, "utf8") > MAX_BODY_BYTES) {
      done(new Error("El cuerpo de la solicitud es demasiado grande."));
      request.destroy();
    }
  });
  request.on("end", function () {
    var payload;
    if (finished) return;
    try {
      payload = body ? JSON.parse(body) : {};
    } catch (error) {
      done(new Error("El cuerpo JSON no es válido."));
      return;
    }
    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      done(new Error("El cuerpo JSON debe ser un objeto."));
      return;
    }
    done(null, payload);
  });
  request.on("error", function (error) {
    done(error);
  });
}

function parseRobotResponse(line) {
  var tokens = line.trim().split(/\s+/);
  var result = {};
  var i;
  var pair;
  var value;

  if (tokens[0] !== "OK") {
    throw new Error("El robot rechazó el comando: " + line.trim());
  }
  result.command = tokens[1] || "";
  for (i = 2; i < tokens.length; i += 1) {
    pair = tokens[i].split("=");
    if (pair.length < 2) continue;
    value = pair.slice(1).join("=");
    if (value === "true") result[pair[0]] = true;
    else if (value === "false") result[pair[0]] = false;
    else if (value !== "" && !isNaN(Number(value))) result[pair[0]] = Number(value);
    else result[pair[0]] = value;
  }
  return result;
}

function RobotSession(socket) {
  this.socket = socket;
  this.buffer = "";
  this.pending = null;
  var self = this;

  socket.setNoDelay(true);
  socket.setTimeout(6000);
  socket.on("data", function (chunk) {
    self.buffer += chunk.toString("utf8");
    self.readResponse();
  });
  socket.on("timeout", function () {
    self.fail(new Error("Se agotó el tiempo de espera del robot."));
    socket.destroy();
  });
  socket.on("error", function (error) {
    self.fail(new Error("No se pudo comunicar con el robot: " + error.message));
  });
  socket.on("close", function () {
    self.fail(new Error("El robot cerró la conexión sin responder."));
  });
}

RobotSession.prototype.readResponse = function () {
  var newline = this.buffer.indexOf("\n");
  var line;
  var callback;
  var result;
  if (newline < 0 || !this.pending) return;
  line = this.buffer.slice(0, newline).replace(/\r$/, "");
  this.buffer = this.buffer.slice(newline + 1);
  callback = this.pending;
  this.pending = null;
  try {
    result = parseRobotResponse(line);
  } catch (error) {
    callback(error);
    return;
  }
  callback(null, result);
};

RobotSession.prototype.fail = function (error) {
  var callback = this.pending;
  this.pending = null;
  if (callback) callback(error);
};

RobotSession.prototype.send = function (command, callback) {
  if (this.pending) {
    callback(new Error("Ya hay un comando del robot en curso."));
    return;
  }
  this.pending = callback;
  this.socket.write(command + "\n", "utf8", function (error) {
    if (error) this.fail(new Error("No se pudo enviar el comando: " + error.message));
  }.bind(this));
};

RobotSession.prototype.close = function () {
  this.socket.end();
  this.socket.destroy();
};

function withRobot(callback) {
  var socket = net.createConnection(ROBOT_PORT, ROBOT_IP);
  var finished = false;
  var session;

  function finish(error, value) {
    if (finished) return;
    finished = true;
    if (session) session.close();
    else socket.destroy();
  }

  socket.setTimeout(6000);
  socket.once("connect", function () {
    session = new RobotSession(socket);
    callback(null, session, finish);
  });
  socket.once("error", function (error) {
    if (session || finished) return;
    finish();
    callback(new Error("No se pudo conectar con el robot en " +
      ROBOT_IP + ":" + ROBOT_PORT + ": " + error.message));
  });
  socket.once("timeout", function () {
    if (session || finished) return;
    finish();
    callback(new Error("Se agotó el tiempo al conectar con el robot."));
  });
}

function commandSequence(session, commands, callback, results) {
  results = results || [];
  if (commands.length === 0) {
    callback(null, results);
    return;
  }
  session.send(commands[0], function (error, result) {
    if (error) {
      callback(error);
      return;
    }
    results.push(result);
    commandSequence(session, commands.slice(1), callback, results);
  });
}

function readPose(session, callback) {
  session.send("pose.get", function (error, pose) {
    if (error) return callback(error);
    if (typeof pose.x_mm !== "number" || typeof pose.y_mm !== "number" ||
        typeof pose.theta_deg !== "number") {
      return callback(new Error("pose.get no devolvió x_mm, y_mm y theta_deg."));
    }
    callback(null, pose);
  });
}

function readYaw(session, callback) {
  session.send("imu.attitude.get", function (error, attitude) {
    if (error) return callback(error);
    if (typeof attitude.yaw !== "number") {
      return callback(new Error("imu.attitude.get no devolvió yaw."));
    }
    callback(null, normalizeAngle(attitude.yaw));
  });
}

function normalizeAngle(angle) {
  return ((angle % 360) + 360) % 360;
}

function angularDifference(target, current) {
  return ((target - current + 180) % 360 + 360) % 360 - 180;
}

function distanceBetween(x1, y1, x2, y2) {
  var dx = x2 - x1;
  var dy = y2 - y1;
  return Math.sqrt(dx * dx + dy * dy);
}

function motionStoppedError() {
  return new Error("Movimiento detenido desde el panel.");
}

function configureGo2Point(session, callback) {
  session.send(
    "robot.go2point.pid.set v_max_giro_deg_s=90 a_max_giro_deg_s2=120 " +
    "v_max_avance_mm_s=300 a_max_avance_mm_s2=100 ts_ms=25",
    callback
  );
}

function configureOrientation(session, callback) {
  session.send(
    "robot.orientation.pid.set kp=2 cruise_deg_s=120 " +
    "a_max_deg_s2=180 ts_ms=25",
    callback
  );
}

function stopMotion(session, callback) {
  var commands = [
    "robot.go2point.stop",
    "robot.orientation.stop",
    "motor.velocity.stop",
    "motor.stop"
  ];
  var errors = [];

  function stopNext() {
    var command;
    if (commands.length === 0) {
      callback(errors.length ? new Error(errors.join(" ")) : null);
      return;
    }
    command = commands.shift();
    session.send(command, function (error) {
      if (error) errors.push(command + ": " + error.message);
      stopNext();
    });
  }
  stopNext();
}

function moveTo(session, x, y, callback, attempt) {
  if (motionCancelled) return callback(motionStoppedError());
  attempt = attempt || 0;
  if (attempt > 3) {
    callback(new Error("El robot no alcanzó el punto de destino después de 3 correcciones."));
    return;
  }
  session.send("motor.velocity.stop", function (stopError) {
    if (stopError) return callback(stopError);
    if (motionCancelled) return callback(motionStoppedError());
    session.send("robot.go2point.set x=" + x + " y=" + y, function (setError) {
      if (setError) return callback(setError);
      if (motionCancelled) {
        session.send("robot.go2point.stop", function () {
          callback(motionStoppedError());
        });
        return;
      }
      poll();
    });
  });

  function poll() {
    var started = Date.now();
    (function check() {
      if (motionCancelled) {
        callback(motionStoppedError());
        return;
      }
      if (Date.now() - started > 60000) {
        session.send("robot.go2point.stop", function () {
          callback(new Error("Se agotó el tiempo de navegación del robot."));
        });
        return;
      }
      session.send("robot.go2point.status", function (error, status) {
        if (error) return callback(error);
        if (typeof status.active !== "boolean") {
          callback(new Error("robot.go2point.status no devolvió active."));
          return;
        }
        if (status.active) {
          setTimeout(check, 50);
          return;
        }
        if (status.valid === false) {
          callback(new Error("go2point terminó con valid=false."));
          return;
        }
        readPose(session, function (poseError, pose) {
          if (poseError) return callback(poseError);
          if (distanceBetween(pose.x_mm, pose.y_mm, x, y) <= 40) {
            callback(null, status);
            return;
          }
          moveTo(session, x, y, callback, attempt + 1);
        });
      });
    }());
  }
}

function turnAndVerify(session, poseTarget, yawReference, yawChange, callback, attempt) {
  var targetYaw = normalizeAngle(yawReference + yawChange);
  var started = Date.now();
  var stableReadings = 0;
  var previousYaw = null;
  attempt = attempt || 0;

  function startTurn(targetPose) {
    if (motionCancelled) return callback(motionStoppedError());
    configureOrientation(session, function (configureError) {
      if (configureError) return callback(configureError);
      if (motionCancelled) return callback(motionStoppedError());
      session.send("robot.orientation.set theta=" + targetPose, function (setError) {
        if (setError) return callback(setError);
        if (motionCancelled) {
          session.send("robot.orientation.stop", function () {
            callback(motionStoppedError());
          });
          return;
        }
        started = Date.now();
        stableReadings = 0;
        previousYaw = null;
        check();
      });
    });
  }

  function check() {
    if (motionCancelled) {
      callback(motionStoppedError());
      return;
    }
    if (Date.now() - started >= 30000) {
      session.send("robot.orientation.stop", function (stopError) {
        if (stopError) return callback(stopError);
        if (attempt >= 3) {
          callback(new Error("El IMU no confirmó el rumbo objetivo después de 3 correcciones."));
          return;
        }
        readPose(session, function (poseError, pose) {
          if (poseError) return callback(poseError);
          readYaw(session, function (yawError, yaw) {
            var remaining;
            if (yawError) return callback(yawError);
            remaining = angularDifference(targetYaw, yaw);
            if (Math.abs(remaining) <= 5) {
              turnAndVerify(session, poseTarget, yawReference, yawChange,
                callback, attempt + 1);
              return;
            }
            attempt += 1;
            startTurn(pose.theta_deg + remaining);
          });
        });
        return;
      });
      return;
    }
    readYaw(session, function (error, yaw) {
      var difference;
      if (error) return callback(error);
      difference = angularDifference(targetYaw, yaw);
      if (Math.abs(difference) <= 5) {
        if (previousYaw !== null &&
            Math.abs(angularDifference(yaw, previousYaw)) <= 5) {
          stableReadings += 1;
        } else {
          stableReadings = 1;
        }
        if (stableReadings >= 3) {
          callback(null, yaw);
          return;
        }
      } else {
        stableReadings = 0;
      }
      previousYaw = yaw;
      setTimeout(check, 100);
    });
  }

  startTurn(poseTarget);
}

function establishOrigin(session, callback) {
  if (motionCancelled) return callback(motionStoppedError());
  if (originReference) {
    callback(null, originReference);
    return;
  }
  session.send("motor.velocity.stop", function (stopError) {
    if (stopError) return callback(stopError);
    if (motionCancelled) return callback(motionStoppedError());
    session.send("pose.set x_mm=0 y_mm=0 theta_deg=0", function (error) {
      if (error) return callback(error);
      readPose(session, function (poseError, pose) {
        if (poseError) return callback(poseError);
        readYaw(session, function (yawError, yaw) {
          if (yawError) return callback(yawError);
          originReference = {
            x_mm: pose.x_mm,
            y_mm: pose.y_mm,
            theta_deg: pose.theta_deg,
            yaw: yaw
          };
          callback(null, originReference);
        });
      });
    });
  });
}

function deliverOrder(order, callback) {
  motionCancelled = false;
  withRobot(function (connectionError, session, finish) {
    var reference;
    var destinationX;
    var destinationY;
    var direction = turnDirections[order.mesa];
    var distance = deliveryDistances[order.mesa];

    if (connectionError) return callback(connectionError);
    function complete(error, travel) {
      finish(error);
      callback(error, travel);
    }
    configureGo2Point(session, function (configError) {
      if (configError) return complete(configError);
      if (motionCancelled) return complete(motionStoppedError());
      establishOrigin(session, function (originError, origin) {
        if (originError) return complete(originError);
        reference = origin;
        readPose(session, function (poseError, pose) {
          var offset;
          var yawError;
          if (poseError) return complete(poseError);
          offset = distanceBetween(pose.x_mm, pose.y_mm, reference.x_mm, reference.y_mm);
          if (offset > 40) {
            complete(new Error("El robot no está en el origen: error de posición " +
              offset.toFixed(1) + " mm."));
            return;
          }
          readYaw(session, function (readError, yaw) {
            var poseOffset;
            if (readError) return complete(readError);
            yawError = angularDifference(reference.yaw, yaw);
            poseOffset = angularDifference(reference.theta_deg, pose.theta_deg);
            function beginRoute() {
              var routeAngle = reference.theta_deg * Math.PI / 180;
              destinationX = reference.x_mm + distance * Math.cos(routeAngle);
              destinationY = reference.y_mm + distance * Math.sin(routeAngle);
              moveTo(session, destinationX, destinationY, function (moveError) {
                if (moveError) return complete(moveError);
                turnAndVerify(session,
                  reference.theta_deg + direction * 90,
                  reference.yaw, direction * 90, function (turnError, finalYaw) {
                    if (turnError) return complete(turnError);
                    complete(null, {
                      yaw_inicio: reference.yaw,
                      theta_inicio: reference.theta_deg,
                      origen_x_mm: reference.x_mm,
                      origen_y_mm: reference.y_mm,
                      direccion_giro: direction,
                      distancia_mm: distance,
                      yaw_entrega: finalYaw
                    });
                  });
              });
            }
            if (Math.abs(yawError) > 5 || Math.abs(poseOffset) > 5) {
              turnAndVerify(session, reference.theta_deg, reference.yaw, 0,
                function (alignError) {
                  if (alignError) return complete(alignError);
                  beginRoute();
                });
            } else {
              beginRoute();
            }
          });
        });
      });
    });
  });
}

function returnOrder(order, callback) {
  motionCancelled = false;
  withRobot(function (connectionError, session, finish) {
    var reference = {
      x_mm: order.origen_x_mm,
      y_mm: order.origen_y_mm,
      theta_deg: order.theta_inicio,
      yaw: order.yaw_inicio
    };
    if (connectionError) return callback(connectionError);
    function complete(error, value) {
      finish(error);
      callback(error, value);
    }
    configureGo2Point(session, function (configError) {
      if (configError) return complete(configError);
      if (motionCancelled) return complete(motionStoppedError());
      turnAndVerify(session,
        reference.theta_deg + order.direccion_giro * 180,
        reference.yaw, order.direccion_giro * 180, function (turnError) {
          if (turnError) return complete(turnError);
          moveTo(session, reference.x_mm, reference.y_mm, function (moveError) {
            if (moveError) return complete(moveError);
            turnAndVerify(session, reference.theta_deg, reference.yaw, 0,
              function (alignError) {
                if (alignError) return complete(alignError);
                readPose(session, function (poseError, pose) {
                  if (poseError) return complete(poseError);
                  if (distanceBetween(pose.x_mm, pose.y_mm,
                      reference.x_mm, reference.y_mm) > 40) {
                    complete(new Error("El robot terminó fuera del origen."));
                    return;
                  }
                  complete(null);
                });
              });
          });
        });
    });
  });
}

function failOrderMotion(order, error) {
  order.estado = "error";
  order.error = error.message;
  console.error("Error en pedido #" + order.id + ":", error.message);
  withRobot(function (connectError, session, finish) {
    if (connectError) {
      console.error(connectError.message);
      return;
    }
    stopMotion(session, function (stopError) {
      if (stopError) console.error("No se pudo detener el robot:", stopError.message);
      finish(null);
    });
  });
}

function findOrder(id) {
  var i;
  for (i = 0; i < orders.length; i += 1) {
    if (orders[i].id === id) return orders[i];
  }
  return null;
}

function publicOrder(order) {
  var result = {};
  var key;
  for (key in order) {
    if (Object.prototype.hasOwnProperty.call(order, key)) result[key] = order[key];
  }
  return result;
}

function hasBusyOrder(exceptOrder) {
  var i;
  for (i = 0; i < orders.length; i += 1) {
    if (orders[i] !== exceptOrder && busyStates.indexOf(orders[i].estado) >= 0) {
      return true;
    }
  }
  return false;
}

function isRobotBusy(exceptOrder) {
  return manualControlActive || hasBusyOrder(exceptOrder);
}

function getRobotStatus(callback) {
  withRobot(function (error, session, finish) {
    if (error) return callback(error);
    commandSequence(session, ["battery.read", "pose.get"],
      function (readError, results) {
        if (readError) {
          finish(readError);
          callback(readError);
          return;
        }
        finish(null);
        callback(null, {
          connected: true,
          host: ROBOT_IP,
          port: ROBOT_PORT,
          battery: results[0],
          pose: results[1],
          attitude: null,
          pico: picoTelemetry
        });
      });
  });
}

function parseInteger(value, label, minimum, maximum) {
  if (typeof value !== "number" || !isFinite(value) ||
      Math.floor(value) !== value || value < minimum || value > maximum) {
    throw new Error(label + " debe ser un entero entre " + minimum + " y " + maximum + ".");
  }
  return value;
}

function stopMotorWatchdog() {
  if (motorWatchdog) {
    clearTimeout(motorWatchdog);
    motorWatchdog = null;
  }
}

function closeManualSession() {
  var finish = manualFinish;
  stopMotorWatchdog();
  manualSession = null;
  manualFinish = null;
  manualCommandPending = false;
  if (finish) finish();
}

function stopManualAfterError() {
  withRobot(function (error, session, finish) {
    if (error) {
      console.error("No se pudo reconectar para detener los motores:", error.message);
      return;
    }
    session.send("motor.stop", function (stopError) {
      finish(stopError);
      if (stopError) {
        console.error("Falló la parada de seguridad:", stopError.message);
      } else {
        manualControlActive = false;
      }
    });
  });
}

function stopManualSession(session) {
  if (manualSession !== session) return;
  if (manualCommandPending) {
    motorWatchdog = setTimeout(function () {
      motorWatchdog = null;
      stopManualSession(session);
    }, 50);
    return;
  }
  manualCommandPending = true;
  session.send("motor.stop", function (motorStopError) {
    manualCommandPending = false;
    if (motorStopError) {
      console.error("Falló la parada automática:", motorStopError.message);
    } else {
      manualControlActive = false;
    }
    closeManualSession();
  });
}

function sendManualPwm(session, left, right, callback) {
  if (manualCommandPending) {
    callback(new Error("Ya hay un comando manual del robot en curso."));
    return;
  }
  manualCommandPending = true;
  session.send("motor.pwm left=" + left + " right=" + right,
    function (commandError, result) {
      manualCommandPending = false;
      if (commandError) {
        var shouldStop = manualControlActive;
        stopMotorWatchdog();
        closeManualSession();
        if (shouldStop) stopManualAfterError();
        else manualControlActive = false;
        callback(commandError);
        return;
      }
      stopMotorWatchdog();
      manualControlActive = true;
      motorWatchdog = setTimeout(function () {
        motorWatchdog = null;
        stopManualSession(session);
      }, 700);
      callback(null, result);
    });
}

function setMotorPwm(left, right, callback) {
  if (manualSession) {
    sendManualPwm(manualSession, left, right, callback);
    return;
  }
  withRobot(function (error, session, finish) {
    if (error) {
      if (!motorWatchdog) manualControlActive = false;
      return callback(error);
    }
    manualSession = session;
    manualFinish = finish;
    sendManualPwm(session, left, right, callback);
  });
}

function apiRequest(request, response, parsedUrl) {
  var pathname = parsedUrl.pathname;
  var match;
  var mesa;
  var order;

  if (request.method === "GET" && pathname === "/api/menu") {
    var temperature = DEFAULT_TEMPERATURE_C;
    if (parsedUrl.query && parsedUrl.query.temperature !== undefined) {
      temperature = Number(parsedUrl.query.temperature);
    }
    if (!isFinite(temperature) || temperature < 5 || temperature > 40) {
      return sendError(response, 400, "La temperatura debe estar entre 5 y 40 °C.");
    }
    sendJson(response, 200, menuResponse(temperature));
    return;
  }
  if (request.method === "GET" && pathname === "/api/health") {
    sendJson(response, 200, {
      ok: true,
      service: "RoboCoffee Edison Host",
      robot: ROBOT_IP + ":" + ROBOT_PORT,
      picoTelemetryReceived: !!picoTelemetry
    });
    return;
  }
  if (request.method === "GET" && pathname === "/api/status") {
    getRobotStatus(function (error, status) {
      if (error) return sendError(response, 503, error.message);
      sendJson(response, 200, status);
    });
    return;
  }
  if (request.method === "GET" && pathname === "/api/robot/imu") {
    withRobot(function (error, session, finish) {
      if (error) return sendError(response, 503, error.message);
      commandSequence(session, ["imu.read", "imu.attitude.get"],
        function (readError, results) {
          if (readError) {
            finish(readError);
            sendError(response, 502, readError.message);
            return;
          }
          finish(null);
          sendJson(response, 200, {
            raw: results[0],
            attitude: results[1],
            sampledAt: Date.now()
          });
        });
    });
    return;
  }
  if (request.method === "GET" && pathname === "/api/orders") {
    sendJson(response, 200, {
      orders: orders.map(publicOrder),
      robotBusy: isRobotBusy(null)
    });
    return;
  }
  if (request.method === "POST" && pathname === "/api/pico/telemetry") {
    readJson(request, function (error, payload) {
      if (error) return sendError(response, 400, error.message);
      picoTelemetry = { receivedAt: new Date().toISOString(), data: payload };
      sendJson(response, 202, { received: true });
    });
    return;
  }
  if (request.method === "POST" && pathname === "/api/orders") {
    readJson(request, function (error, payload) {
      if (error) return sendError(response, 400, error.message);
      try {
        mesa = parseInteger(payload.mesa, "La mesa", 1, 4);
      } catch (validationError) {
        return sendError(response, 400, validationError.message);
      }
      if (["Espresso", "Latte", "Capuccino", "Americano"].indexOf(payload.cafe) < 0) {
        return sendError(response, 400, "Selecciona un café válido.");
      }
      if (payload.presentacion !== undefined &&
          payload.presentacion !== "caliente" &&
          !(payload.cafe === "Americano" && payload.presentacion === "frio")) {
        return sendError(response, 400, "Solo el Americano se puede pedir frío.");
      }
      if (typeof payload.nombre !== "string" ||
          payload.nombre.trim().length < 1 || payload.nombre.trim().length > 60) {
        return sendError(response, 400, "El nombre debe tener entre 1 y 60 caracteres.");
      }
      order = {
        id: nextOrderId++,
        mesa: mesa,
        nombre: payload.nombre.trim(),
        cafe: payload.cafe,
        presentacion: payload.presentacion || "caliente",
        estado: "pendiente",
        createdAt: new Date().toISOString()
      };
      orders.push(order);
      sendJson(response, 201, { order: publicOrder(order) });
    });
    return;
  }
  match = pathname.match(/^\/api\/orders\/(\d+)\/(deliver|received)$/);
  if (request.method === "POST" && match) {
    order = findOrder(Number(match[1]));
    if (!order) return sendError(response, 404, "No existe ese pedido.");
    if (match[2] === "deliver") {
      if (order.estado !== "pendiente") {
        return sendError(response, 409, "El pedido ya no está pendiente.");
      }
      if (isRobotBusy(order)) {
        return sendError(response, 409, "El robot está ocupado o requiere revisión.");
      }
      order.estado = "saliendo";
      order.error = null;
      sendJson(response, 202, { order: publicOrder(order) });
      deliverOrder(order, function (error, travel) {
        if (error) {
          failOrderMotion(order, error);
          return;
        }
        Object.keys(travel).forEach(function (key) { order[key] = travel[key]; });
        order.estado = "esperando_cliente";
      });
      return;
    }
    if (order.estado !== "esperando_cliente") {
      return sendError(response, 409, "El robot todavía no está esperando al cliente.");
    }
    order.estado = "regresando";
    sendJson(response, 202, { order: publicOrder(order) });
    returnOrder(order, function (error) {
      if (error) {
        failOrderMotion(order, error);
        return;
      }
      order.estado = "completado";
      order.error = null;
    });
    return;
  }
  match = pathname.match(/^\/api\/customer\/orders\/(\d+)$/);
  if (request.method === "GET" && match) {
    order = findOrder(Number(match[1]));
    if (!order) return sendError(response, 404, "No existe ese pedido.");
    sendJson(response, 200, {
      order: {
        id: order.id,
        mesa: order.mesa,
        cafe: order.cafe,
        presentacion: order.presentacion,
        estado: order.estado,
        createdAt: order.createdAt
      }
    });
    return;
  }
  if (request.method === "POST" && pathname === "/api/robot/stop") {
    stopMotorWatchdog();
    manualControlActive = true;
    motionCancelled = true;
    if (manualSession) {
      (function stopConnectedSession(session) {
        if (manualSession !== session) {
          withRobot(function (error, stopSession, finish) {
            if (error) return sendError(response, 503, error.message);
            stopMotion(stopSession, function (stopError) {
              finish(stopError);
              if (stopError) return sendError(response, 502, stopError.message);
              manualControlActive = false;
              sendJson(response, 200, { stopped: true });
            });
          });
          return;
        }
        if (manualCommandPending) {
          setTimeout(function () { stopConnectedSession(session); }, 25);
          return;
        }
        stopMotorWatchdog();
        manualCommandPending = true;
        session.send("motor.stop", function (stopError) {
          manualCommandPending = false;
          closeManualSession();
          if (stopError) return sendError(response, 502, stopError.message);
          manualControlActive = false;
          sendJson(response, 200, { stopped: true });
        });
      }(manualSession));
      return;
    }
    withRobot(function (error, session, finish) {
      if (error) return sendError(response, 503, error.message);
      stopMotion(session, function (stopError) {
        finish(stopError);
        if (stopError) return sendError(response, 502, stopError.message);
        manualControlActive = false;
        sendJson(response, 200, { stopped: true });
      });
    });
    return;
  }
  if (request.method === "POST" && pathname === "/api/robot/motor") {
    if (hasBusyOrder()) {
      return sendError(response, 409, "El control manual está bloqueado durante una entrega.");
    }
    readJson(request, function (error, payload) {
      var left;
      var right;
      if (error) return sendError(response, 400, error.message);
      try {
        left = parseInteger(payload.left, "left", -70, 70);
        right = parseInteger(payload.right, "right", -70, 70);
      } catch (validationError) {
        return sendError(response, 400, validationError.message);
      }
      manualControlActive = true;
      setMotorPwm(left, right, function (commandError, result) {
        if (commandError) return sendError(response, 503, commandError.message);
        sendJson(response, 200, { command: result, watchdogMs: 700 });
      });
    });
    return;
  }
  sendError(response, 404, "Ruta API no encontrada.");
}

function serveStatic(request, response, pathname) {
  var files = {
    "/": "customer.html",
    "/cliente": "customer.html",
    "/menu": "customer.html",
    "/customer.html": "customer.html",
    "/customer.css": "customer.css",
    "/customer.js": "customer.js",
    "/trabajador": "index.html",
    "/index.html": "index.html",
    "/styles.css": "styles.css",
    "/worker.css": "styles.css",
    "/app.js": "app.js",
    "/worker.js": "app.js"
  };
  var file = files[pathname];
  var contentTypes = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8"
  };
  if (request.method === "GET" && pathname === "/trabajador") {
    response.writeHead(302, {
      Location: "/index.html",
      "Cache-Control": "no-store"
    });
    response.end();
    return;
  }
  if (request.method !== "GET" || !file) {
    sendError(response, 404, "Página no encontrada.");
    return;
  }
  fs.readFile(path.join(PUBLIC_DIR, file), function (error, contents) {
    if (error) {
      console.error("No se pudo leer " + file + ":", error.message);
      return sendError(response, 500, "No se pudo cargar la interfaz.");
    }
    response.writeHead(200, {
      "Content-Type": contentTypes[path.extname(file)],
      "Cache-Control": "no-store"
    });
    response.end(contents);
  });
}

var server = http.createServer(function (request, response) {
  var parsed = url.parse(request.url, true);
  if (parsed.pathname.indexOf("/api/") === 0) {
    apiRequest(request, response, parsed);
    return;
  }
  serveStatic(request, response, parsed.pathname);
});

server.listen(PORT, HOST, function () {
  console.log("RoboCoffee disponible en http://" + HOST + ":" + PORT);
  console.log("ESP32 configurada en " + ROBOT_IP + ":" + ROBOT_PORT);
});

server.on("error", function (error) {
  console.error("No se pudo iniciar el servidor:", error.message);
  process.exit(1);
});
