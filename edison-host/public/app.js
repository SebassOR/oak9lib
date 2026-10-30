(function () {
  "use strict";

  var statusEl = document.getElementById("connection-badge");
  var ordersList = document.getElementById("orders-list");
  var testMessage = document.getElementById("test-message");
  var modal = document.getElementById("order-modal");
  var imuDebugModal = document.getElementById("imu-debug-modal");
  var pollingTimer = null;
  var activeDrive = false;
  var driveTimer = null;
  var driveRequestPending = false;
  var driveStopPending = false;
  var imuTimer = null;
  var imuDebugOpen = false;
  var imuRequestPending = false;
  var imuDebugSession = 0;
  var imuSamples = [];
  var lastOrders = [];
  var imuSeries = [
    { key: "roll", label: "Roll", color: "#4886b5" },
    { key: "pitch", label: "Pitch", color: "#d28a51" },
    { key: "yaw", label: "Yaw", color: "#7c68a6" }
  ];

  function request(path, method, body, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open(method, path, true);
    xhr.setRequestHeader("Content-Type", "application/json");
    xhr.onreadystatechange = function () {
      var result;
      if (xhr.readyState !== 4) return;
      try {
        result = xhr.responseText ? JSON.parse(xhr.responseText) : {};
      } catch (error) {
        callback(new Error("El servidor devolvió una respuesta inválida."));
        return;
      }
      if (xhr.status < 200 || xhr.status >= 300) {
        callback(new Error(result.error || "La solicitud falló (" + xhr.status + ")."));
        return;
      }
      callback(null, result);
    };
    xhr.onerror = function () { callback(new Error("No hay conexión con el host Edison.")); };
    xhr.send(body ? JSON.stringify(body) : null);
  }

  function setConnection(state, text) {
    statusEl.className = "connection-badge " + state;
    statusEl.lastChild.textContent = text;
  }

  function formatValue(value, digits) {
    return typeof value === "number" ? value.toFixed(digits) : "--";
  }

  function normalizeHeading(value) {
    return typeof value === "number" ? ((value % 360) + 360) % 360 : value;
  }

  function setImuDebugStatus(message, isError) {
    var status = document.getElementById("imu-debug-status");
    status.textContent = message;
    status.className = isError ? "imu-debug-status error" : "imu-debug-status";
  }

  function formatRawImu(raw) {
    var values = [];
    var key;
    if (!raw || typeof raw !== "object") return String(raw);
    for (key in raw) {
      if (Object.prototype.hasOwnProperty.call(raw, key) && key !== "command") {
        values.push(key + ": " +
          (typeof raw[key] === "number" ? raw[key].toFixed(3) : String(raw[key])));
      }
    }
    return values.length ? values.join(" · ") : JSON.stringify(raw);
  }

  function drawImuChart() {
    var canvas = document.getElementById("imu-chart");
    var bounds = canvas.getBoundingClientRect();
    var ratio = window.devicePixelRatio || 1;
    var width = bounds.width;
    var height = bounds.height;
    var context;
    var left = 54;
    var right = 10;
    var top = 8;
    var bottom = 20;
    var plotWidth = width - left - right;
    var plotHeight = height - top - bottom;
    var rowHeight = plotHeight / imuSeries.length;
    var now = Date.now();
    var windowStart = now - 30000;
    var seriesIndex;
    var sampleIndex;
    var sample;
    var series;
    var values;
    var value;
    var previousYaw;
    var minimum;
    var maximum;
    var padding;
    var range;
    var rowTop;
    var plotTop;
    var plotBottom;
    var x;
    var y;
    var gridIndex;

    if (!width || !height) return;
    canvas.width = Math.round(width * ratio);
    canvas.height = Math.round(height * ratio);
    context = canvas.getContext("2d");
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    context.clearRect(0, 0, width, height);
    context.font = "10px Segoe UI, sans-serif";

    for (seriesIndex = 0; seriesIndex < imuSeries.length; seriesIndex += 1) {
      series = imuSeries[seriesIndex];
      values = [];
      previousYaw = null;
      for (sampleIndex = 0; sampleIndex < imuSamples.length; sampleIndex += 1) {
        sample = imuSamples[sampleIndex];
        value = sample[series.key];
        if (typeof value !== "number" || !isFinite(value)) {
          values.push(null);
          continue;
        }
        if (series.key === "yaw" && previousYaw !== null) {
          while (value - previousYaw > 180) value -= 360;
          while (value - previousYaw < -180) value += 360;
        }
        values.push(value);
        if (series.key === "yaw") previousYaw = value;
      }

      minimum = Infinity;
      maximum = -Infinity;
      for (sampleIndex = 0; sampleIndex < values.length; sampleIndex += 1) {
        if (values[sampleIndex] === null) continue;
        minimum = Math.min(minimum, values[sampleIndex]);
        maximum = Math.max(maximum, values[sampleIndex]);
      }
      if (minimum === Infinity) {
        minimum = -1;
        maximum = 1;
      }
      padding = Math.max((maximum - minimum) * 0.15, 1);
      minimum -= padding;
      maximum += padding;
      range = maximum - minimum;
      rowTop = top + seriesIndex * rowHeight;
      plotTop = rowTop + 5;
      plotBottom = rowTop + rowHeight - 8;

      context.fillStyle = "#65736a";
      context.textAlign = "left";
      context.fillText(series.label + " (°)", 2, plotTop + 4);
      context.textAlign = "right";
      for (gridIndex = 0; gridIndex < 3; gridIndex += 1) {
        y = plotTop + (plotBottom - plotTop) * gridIndex / 2;
        value = maximum - range * gridIndex / 2;
        context.strokeStyle = "#edf0ec";
        context.beginPath();
        context.moveTo(left, y);
        context.lineTo(width - right, y);
        context.stroke();
        context.fillStyle = "#9aa29d";
        context.fillText(value.toFixed(1), left - 7, y + 3);
      }

      context.strokeStyle = series.color;
      context.lineWidth = 1.8;
      context.beginPath();
      var hasPoint = false;
      for (sampleIndex = 0; sampleIndex < values.length; sampleIndex += 1) {
        if (values[sampleIndex] === null) {
          hasPoint = false;
          continue;
        }
        sample = imuSamples[sampleIndex];
        x = left + Math.max(0, Math.min(1,
          (sample.time - windowStart) / 30000)) * plotWidth;
        y = plotBottom - (values[sampleIndex] - minimum) / range *
          (plotBottom - plotTop);
        if (hasPoint) context.lineTo(x, y);
        else context.moveTo(x, y);
        hasPoint = true;
      }
      context.stroke();
    }

    context.fillStyle = "#9aa29d";
    context.textAlign = "left";
    context.fillText("-30 s", left, height - 2);
    context.textAlign = "center";
    context.fillText("-15 s", left + plotWidth / 2, height - 2);
    context.textAlign = "right";
    context.fillText("ahora", width - right, height - 2);
  }

  function pollImu() {
    var session = imuDebugSession;
    if (!imuDebugOpen || imuRequestPending) return;
    imuRequestPending = true;
    request("/api/robot/imu", "GET", null, function (error, result) {
      var attitude;
      var sample;
      imuRequestPending = false;
      if (!imuDebugOpen || session !== imuDebugSession) return;
      if (error) {
        setImuDebugStatus("No se pudo leer el MPU: " + error.message, true);
        return;
      }
      attitude = result.attitude;
      if (!attitude ||
          typeof attitude.roll !== "number" || !isFinite(attitude.roll) ||
          typeof attitude.pitch !== "number" || !isFinite(attitude.pitch) ||
          typeof attitude.yaw !== "number" || !isFinite(attitude.yaw)) {
        setImuDebugStatus("El robot no devolvió roll, pitch y yaw válidos.", true);
        return;
      }
      sample = {
        time: Date.now(),
        roll: attitude.roll,
        pitch: attitude.pitch,
        yaw: attitude.yaw
      };
      imuSamples.push(sample);
      if (imuSamples.length > 120) imuSamples.shift();
      document.getElementById("imu-roll").textContent = sample.roll.toFixed(1) + "°";
      document.getElementById("imu-pitch").textContent = sample.pitch.toFixed(1) + "°";
      document.getElementById("imu-yaw").textContent = sample.yaw.toFixed(1) + "°";
      document.getElementById("imu-raw-values").textContent = formatRawImu(result.raw);
      setImuDebugStatus("Lectura en vivo · intervalo solicitado: 250 ms.", false);
      drawImuChart();
    });
  }

  function openImuDebug() {
    if (imuDebugOpen) return;
    imuDebugOpen = true;
    imuDebugSession += 1;
    imuSamples = [];
    imuDebugModal.className = "modal-backdrop debug-backdrop open";
    imuDebugModal.setAttribute("aria-hidden", "false");
    document.getElementById("imu-raw-values").textContent = "Esperando datos del MPU…";
    setImuDebugStatus("Conectando al MPU…", false);
    drawImuChart();
    pollImu();
    imuTimer = setInterval(pollImu, 250);
    document.getElementById("imu-debug-close").focus();
  }

  function closeImuDebug() {
    if (!imuDebugOpen) return;
    imuDebugOpen = false;
    imuDebugSession += 1;
    if (imuTimer) {
      clearInterval(imuTimer);
      imuTimer = null;
    }
    imuDebugModal.className = "modal-backdrop debug-backdrop";
    imuDebugModal.setAttribute("aria-hidden", "true");
    document.getElementById("imu-debug-open").focus();
  }

  function refreshStatus() {
    request("/api/status", "GET", null, function (error, status) {
      var voltage;
      if (error) {
        setConnection("disconnected", "Robot desconectado");
        document.getElementById("battery-value").textContent = "--";
        document.getElementById("battery-detail").textContent = error.message;
        document.getElementById("position-value").textContent = "-- / --";
        document.getElementById("heading-value").textContent = "--°";
        document.getElementById("host-address").textContent = "Revisa IP y conexión";
        return;
      }
      setConnection("connected", "Robot conectado");
      document.getElementById("host-address").textContent = status.host + ":" + status.port;
      voltage = status.battery && status.battery.voltage;
      document.getElementById("battery-value").textContent =
        typeof voltage === "number" ? voltage.toFixed(2) + " V" : "Conectada";
      document.getElementById("battery-detail").textContent =
        typeof status.battery.raw === "number" ? "Lectura ADC " + status.battery.raw : "Lectura disponible";
      document.getElementById("position-value").textContent =
        formatValue(status.pose.x_mm, 0) + " / " + formatValue(status.pose.y_mm, 0);
      document.getElementById("heading-value").textContent =
        status.attitude ? formatValue(normalizeHeading(status.attitude.yaw), 1) + "°" : "--°";
      document.getElementById("attitude-detail").textContent =
        status.attitude ? "Roll " + formatValue(status.attitude.roll, 1) +
          "° · Pitch " + formatValue(status.attitude.pitch, 1) + "°" :
          "Abre DEBUG MPU para leer orientación";
      document.getElementById("last-updated").textContent =
        "Actualizado " + new Date().toLocaleTimeString();
      updatePico(status.pico);
    });
  }

  function updatePico(pico) {
    var display;
    if (!pico) {
      document.getElementById("pico-value").textContent = "Sin datos";
      document.getElementById("pico-detail").textContent = "Publica en /api/pico/telemetry";
      return;
    }
    display = pico.data && (pico.data.status || pico.data.state || pico.data.message);
    if (!display) display = "En línea";
    if (typeof display !== "string") display = JSON.stringify(display);
    document.getElementById("pico-value").textContent =
      display.length > 23 ? display.slice(0, 20) + "…" : display;
    document.getElementById("pico-detail").textContent =
      "Último dato " + new Date(pico.receivedAt).toLocaleTimeString();
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return {
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
      }[character];
    });
  }

  function statusLabel(state) {
    return {
      pendiente: "Pendiente",
      saliendo: "En camino",
      esperando_cliente: "Esperando cliente",
      regresando: "Regresando",
      completado: "Completado",
      error: "Requiere revisión"
    }[state] || state;
  }

  function renderOrders(response) {
    var orders = response.orders || [];
    var html = "";
    var i;
    var order;
    var action;
    lastOrders = orders;
    document.getElementById("order-count").textContent = orders.length;
    if (orders.length === 0) {
      ordersList.innerHTML = '<div class="empty-state"><span>☕</span><strong>Aún no hay pedidos</strong><p>Agrega un pedido de prueba para iniciar el flujo.</p></div>';
      return;
    }
    for (i = orders.length - 1; i >= 0; i -= 1) {
      order = orders[i];
      action = "";
      if (order.estado === "pendiente") {
        action = '<button class="order-action" data-action="deliver" data-id="' +
          order.id + '"' + (response.robotBusy ? " disabled" : "") +
          '>Enviar robot →</button>';
      } else if (order.estado === "esperando_cliente") {
        action = '<button class="order-action" data-action="received" data-id="' +
          order.id + '">Confirmar recepción →</button>';
      }
      html += '<article class="order-card"><div class="order-main"><span class="order-coffee">☕</span>' +
        '<div><div class="order-name">' + escapeHtml(order.nombre) +
        ' <span class="order-info">· Mesa ' + order.mesa + '</span></div><div class="order-info">' +
        escapeHtml(order.cafe) + ' · ' + escapeHtml(order.presentacion || "caliente") +
        ' · Pedido #' + order.id + '</div>' +
        (order.error ? '<div class="order-error">' + escapeHtml(order.error) + '</div>' : "") +
        '</div></div><div class="order-right"><span class="status-pill status-' +
        escapeHtml(order.estado) + '">' + escapeHtml(statusLabel(order.estado)) +
        '</span>' + action + '</div></article>';
    }
    ordersList.innerHTML = html;
  }

  function refreshOrders() {
    request("/api/orders", "GET", null, function (error, result) {
      if (!error) renderOrders(result);
    });
  }

  function refreshAll() {
    if (!imuDebugOpen) refreshStatus();
    refreshOrders();
  }

  function setModal(open) {
    modal.className = open ? "modal-backdrop open" : "modal-backdrop";
    modal.setAttribute("aria-hidden", open ? "false" : "true");
    if (open) document.getElementById("customer-name").focus();
  }

  function sendStop() {
    activeDrive = false;
    driveStopPending = false;
    if (driveTimer) {
      clearInterval(driveTimer);
      driveTimer = null;
    }
    if (driveRequestPending) {
      driveStopPending = true;
      return;
    }
    request("/api/robot/stop", "POST", {}, function (error) {
      testMessage.textContent = error ? "No se pudo detener el robot: " + error.message : "Robot detenido.";
      testMessage.style.color = error ? "#b44e40" : "#397253";
    });
  }

  function sendDrive(button) {
    if (driveRequestPending) return;
    driveRequestPending = true;
    request("/api/robot/motor", "POST", {
      left: Number(button.getAttribute("data-left")),
      right: Number(button.getAttribute("data-right"))
    }, function (error) {
      driveRequestPending = false;
      if (driveStopPending) {
        sendStop();
        return;
      }
      if (error) {
        activeDrive = false;
        if (driveTimer) {
          clearInterval(driveTimer);
          driveTimer = null;
        }
        testMessage.textContent = error.message;
        testMessage.style.color = "#b44e40";
        return;
      }
      testMessage.textContent = "Motores activos · potencia limitada · suelta para detener.";
      testMessage.style.color = "#397253";
    });
  }

  document.getElementById("refresh-button").addEventListener("click", refreshAll);
  document.getElementById("new-order-button").addEventListener("click", function () { setModal(true); });
  document.getElementById("close-modal").addEventListener("click", function () { setModal(false); });
  modal.addEventListener("click", function (event) {
    if (event.target === modal) setModal(false);
  });
  document.getElementById("order-form").addEventListener("submit", function (event) {
    var form = event.currentTarget;
    event.preventDefault();
    document.getElementById("form-error").textContent = "";
    request("/api/orders", "POST", {
      nombre: form.nombre.value,
      mesa: Number(form.mesa.value),
      cafe: form.cafe.value
    }, function (error) {
      if (error) {
        document.getElementById("form-error").textContent = error.message;
        return;
      }
      form.reset();
      setModal(false);
      refreshOrders();
    });
  });
  ordersList.addEventListener("click", function (event) {
    var button = event.target;
    var action;
    var id;
    if (button.tagName !== "BUTTON") return;
    action = button.getAttribute("data-action");
    id = button.getAttribute("data-id");
    if (!action || !id) return;
    button.disabled = true;
    request("/api/orders/" + id + "/" + action, "POST", {}, function (error) {
      if (error) window.alert(error.message);
      refreshOrders();
    });
  });
  document.getElementById("stop-button").addEventListener("click", sendStop);
  document.getElementById("pad-stop").addEventListener("click", sendStop);
  document.getElementById("imu-debug-open").addEventListener("click", openImuDebug);
  document.getElementById("imu-debug-close").addEventListener("click", closeImuDebug);
  imuDebugModal.addEventListener("click", function (event) {
    if (event.target === imuDebugModal) closeImuDebug();
  });
  document.addEventListener("keydown", function (event) {
    if (imuDebugOpen && event.key === "Escape") closeImuDebug();
  });

  Array.prototype.forEach.call(document.querySelectorAll(".drive-button[data-left]"), function (button) {
    button.addEventListener("pointerdown", function (event) {
      event.preventDefault();
      if (activeDrive) return;
      activeDrive = true;
      sendDrive(button);
      driveTimer = setInterval(function () {
        if (activeDrive) sendDrive(button);
      }, 400);
    });
    function release() {
      if (!activeDrive) return;
      activeDrive = false;
      if (driveTimer) {
        clearInterval(driveTimer);
        driveTimer = null;
      }
      sendStop();
    }
    button.addEventListener("pointerup", release);
    button.addEventListener("pointerleave", release);
    button.addEventListener("pointercancel", release);
  });

  document.getElementById("clock").textContent = new Date().toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit"
  });
  setInterval(function () {
    document.getElementById("clock").textContent = new Date().toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit"
    });
  }, 15000);
  refreshAll();
  pollingTimer = setInterval(function () {
    refreshOrders();
  }, 3000);
  window.addEventListener("resize", function () {
    if (imuDebugOpen) drawImuChart();
  });
  window.addEventListener("beforeunload", function () {
    if (pollingTimer) clearInterval(pollingTimer);
    if (imuTimer) clearInterval(imuTimer);
    if (activeDrive) sendStop();
  });
}());
