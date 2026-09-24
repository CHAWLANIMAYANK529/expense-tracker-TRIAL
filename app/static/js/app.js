(function () {
  function moneyTick(value) {
    return "₹" + Number(value).toLocaleString("en-US");
  }

  function axisOptions() {
    return {
      y: {
        beginAtZero: true,
        ticks: { callback: moneyTick },
        grid: { color: "#efe8dc" },
      },
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
    };
  }

  window.renderFinanceCharts = function (data) {
    if (!window.Chart) {
      ["categoryChart", "timeChart", "monthChart"].forEach(function (id) {
        const canvas = document.getElementById(id);
        if (!canvas) return;
        const note = document.createElement("p");
        note.className = "empty-copy";
        note.textContent = "Charts could not be loaded. Check your network connection and refresh.";
        canvas.replaceWith(note);
      });
      return;
    }
    if (!data) return;
    Chart.defaults.font.family = '"Source Sans 3", sans-serif';
    Chart.defaults.color = "#3e4a42";

    const category = document.getElementById("categoryChart");
    if (category && data.category_labels && data.category_labels.length) {
      new Chart(category, {
        type: "doughnut",
        data: {
          labels: data.category_labels,
          datasets: [{
            data: data.category_values,
            backgroundColor: data.category_colors,
            borderWidth: 0,
          }],
        },
        options: {
          plugins: { legend: { position: "bottom" } },
          cutout: "58%",
        },
      });
    }

    const time = document.getElementById("timeChart");
    if (time && data.time_labels && data.time_labels.length) {
      new Chart(time, {
        type: "line",
        data: {
          labels: data.time_labels,
          datasets: [{
            label: "Spending",
            data: data.time_values,
            borderColor: "#1f6b4a",
            backgroundColor: "rgba(31, 107, 74, 0.12)",
            fill: true,
            tension: 0.25,
            pointRadius: 2,
          }],
        },
        options: { plugins: { legend: { display: false } }, scales: axisOptions() },
      });
    }

    const month = document.getElementById("monthChart");
    if (month && data.month_labels && data.month_labels.length) {
      new Chart(month, {
        type: "bar",
        data: {
          labels: data.month_labels,
          datasets: [{
            label: "Spending",
            data: data.month_values,
            backgroundColor: "#1f4b3a",
            borderRadius: 4,
            maxBarThickness: 48,
          }],
        },
        options: { plugins: { legend: { display: false } }, scales: axisOptions() },
      });
    }
  };

  document.querySelectorAll("form[data-loading]").forEach(function (form) {
    form.addEventListener("submit", function () {
      const button = form.querySelector("[type=submit]");
      if (!button) return;
      button.disabled = true;
      button.dataset.originalLabel = button.textContent;
      button.textContent = "Working…";
    });
  });
})();
