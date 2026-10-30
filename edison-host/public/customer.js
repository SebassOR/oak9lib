(function () {
  "use strict";

  var temperatureInput = document.getElementById("temperature");
  var temperatureOutput = document.getElementById("temperature-output");
  var recommendation = null;
  var selectedCoffee = "";
  var orderId = null;
  var orderTimer = null;
  var recommendationChanged = false;

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
        callback(new Error(result.error || "La solicitud no se pudo completar."));
        return;
      }
      callback(null, result);
    };
    xhr.onerror = function () {
      callback(new Error("No hay conexión con el servidor de RoboCoffee."));
    };
    xhr.send(body ? JSON.stringify(body) : null);
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return {
        "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
      }[character];
    });
  }

  function setSelectedCoffee(coffee, shouldFocus) {
    var cards = document.querySelectorAll(".coffee-card");
    var i;
    var card;
    selectedCoffee = coffee;
    document.getElementById("selected-coffee").textContent = coffee;
    document.getElementById("submit-order").disabled = !coffee;
    for (i = 0; i < cards.length; i += 1) {
      card = cards[i];
      card.className = card.getAttribute("data-coffee") === coffee ?
        "coffee-card selected" : "coffee-card";
      if (card.getAttribute("data-coffee") === coffee && shouldFocus) {
        card.setAttribute("aria-pressed", "true");
      } else {
        card.setAttribute("aria-pressed", "false");
      }
    }
    updateColdOption();
    if (shouldFocus) {
      var selectedInput = document.querySelector('input[name="presentacion"][value="caliente"]');
      if (selectedInput) selectedInput.checked = true;
    }
  }

  function renderMenu(data) {
    var html = "";
    var coffees = data.coffees || [];
    var i;
    var coffee;
    var isSelected;
    recommendation = data.recommendation;
    document.getElementById("climate-label").textContent = recommendation.clima.toUpperCase();
    document.getElementById("recommendation-title").textContent = recommendation.titulo;
    document.getElementById("recommendation-detail").textContent = recommendation.detalle;
    document.getElementById("temperature-label").textContent = data.temperatureC + " °C";
    if (!recommendationChanged && !selectedCoffee) selectedCoffee = recommendation.cafe;
    for (i = 0; i < coffees.length; i += 1) {
      coffee = coffees[i];
      isSelected = selectedCoffee === coffee.id;
      html += '<button type="button" class="coffee-card' +
        (isSelected ? ' selected' : '') + '" data-coffee="' +
        escapeHtml(coffee.id) + '" aria-pressed="' + isSelected + '">' +
        '<span class="coffee-art">' + coffeeIcon(coffee.id) + '</span>' +
        '<span class="coffee-copy"><span class="coffee-name">' +
        escapeHtml(coffee.id) + '</span><span class="coffee-description">' +
        escapeHtml(coffee.description) + '</span><span class="coffee-note">' +
        escapeHtml(coffee.note) + '</span></span>' +
        (coffee.recommended ? '<span class="recommended-tag">RECOMENDADO</span>' : '') +
        '<span class="coffee-check">✓</span></button>';
    }
    document.getElementById("coffee-menu").innerHTML = html;
    setSelectedCoffee(selectedCoffee, false);
  }

  function coffeeIcon(coffee) {
    return {
      Espresso: "☕",
      Latte: "🥛",
      Americano: "◉"
    }[coffee] || "☕";
  }

  function loadMenu() {
    var temperature = Number(temperatureInput.value);
    temperatureOutput.textContent = temperature + " °C";
    request("/api/menu?temperature=" + temperature, "GET", null, function (error, data) {
      if (error) {
        document.getElementById("form-error").textContent = error.message;
        return;
      }
      renderMenu(data);
    });
  }

  function updateColdOption() {
    var coldInput = document.querySelector('input[name="presentacion"][value="frio"]');
    var coldOption = document.getElementById("cold-option");
    var coldAvailable = selectedCoffee === "Americano";
    coldInput.disabled = !coldAvailable;
    coldOption.className = coldAvailable ? "presentation-option" : "presentation-option disabled";
    if (!coldAvailable && coldInput.checked) {
      document.querySelector('input[name="presentacion"][value="caliente"]').checked = true;
    }
  }

  function statusDetails(state) {
    return {
      pendiente: ["Pedido recibido", "El equipo está preparando tu pedido.", "Pendiente"],
      saliendo: ["¡Tu café va en camino!", "RoboCoffee está llevando tu pedido a la mesa.", "En camino"],
      esperando_cliente: ["¡RoboCoffee llegó!", "Recoge tu café y confirma cuando lo tengas.", "Esperando en tu mesa"],
      regresando: ["¡Que lo disfrutes!", "RoboCoffee está regresando a su estación.", "Regresando"],
      completado: ["¡Gracias por tu visita!", "La entrega terminó. ¡Esperamos verte pronto!", "Completado"],
      error: ["Avisa a nuestro equipo", "El trabajador revisará el estado de tu pedido.", "Requiere ayuda"]
    }[state] || ["Estado de tu pedido", "Actualizando el estado…", state];
  }

  function refreshOrder() {
    if (!orderId) return;
    request("/api/customer/orders/" + orderId, "GET", null, function (error, result) {
      var status;
      var details;
      if (error) {
        document.getElementById("tracking-detail").textContent = error.message;
        return;
      }
      status = result.order.estado;
      details = statusDetails(status);
      document.getElementById("tracking-title").textContent = details[0];
      document.getElementById("tracking-detail").textContent = details[1];
      document.getElementById("tracking-status").textContent = details[2];
      document.getElementById("received-button").hidden = status !== "esperando_cliente";
      if (status === "completado" || status === "error") {
        if (orderTimer) clearInterval(orderTimer);
        orderTimer = null;
      }
    });
  }

  document.getElementById("coffee-menu").addEventListener("click", function (event) {
    var card = event.target;
    while (card && card !== this && !card.getAttribute("data-coffee")) {
      card = card.parentNode;
    }
    if (!card || card === this) return;
    recommendationChanged = true;
    setSelectedCoffee(card.getAttribute("data-coffee"), true);
  });

  document.getElementById("choose-recommended").addEventListener("click", function () {
    if (!recommendation) return;
    recommendationChanged = true;
    setSelectedCoffee(recommendation.cafe, true);
    document.getElementById("customer-name").focus();
  });

  temperatureInput.addEventListener("input", function () {
    temperatureOutput.textContent = temperatureInput.value + " °C";
  });
  temperatureInput.addEventListener("change", loadMenu);

  document.getElementById("customer-order-form").addEventListener("submit", function (event) {
    var form = event.currentTarget;
    var presentation;
    var errorNode = document.getElementById("form-error");
    event.preventDefault();
    if (!selectedCoffee) {
      errorNode.textContent = "Selecciona un café del menú.";
      return;
    }
    presentation = form.querySelector('input[name="presentacion"]:checked').value;
    errorNode.textContent = "";
    document.getElementById("submit-order").disabled = true;
    request("/api/orders", "POST", {
      nombre: form.nombre.value,
      mesa: Number(form.mesa.value),
      cafe: selectedCoffee,
      presentacion: presentation
    }, function (error, result) {
      if (error) {
        errorNode.textContent = error.message;
        document.getElementById("submit-order").disabled = false;
        return;
      }
      orderId = result.order.id;
      document.getElementById("tracking-id").textContent = orderId;
      document.getElementById("order-tracking").hidden = false;
      form.hidden = true;
      document.getElementById("order-tracking").scrollIntoView();
      refreshOrder();
      orderTimer = setInterval(refreshOrder, 3000);
    });
  });

  document.getElementById("received-button").addEventListener("click", function () {
    var button = this;
    button.disabled = true;
    request("/api/orders/" + orderId + "/received", "POST", {}, function (error) {
      if (error) {
        document.getElementById("tracking-detail").textContent = error.message;
        button.disabled = false;
        return;
      }
      refreshOrder();
    });
  });

  document.getElementById("another-order").addEventListener("click", function () {
    if (orderTimer) clearInterval(orderTimer);
    orderTimer = null;
    orderId = null;
    document.getElementById("customer-order-form").reset();
    document.getElementById("customer-order-form").hidden = false;
    document.getElementById("order-tracking").hidden = true;
    document.getElementById("received-button").disabled = false;
    window.scrollTo(0, 0);
  });

  loadMenu();
}());
