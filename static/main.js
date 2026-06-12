document.addEventListener("DOMContentLoaded", () => {
  const loginForm = document.getElementById("login-form");
  const analyzeBtn = document.getElementById("analyze-btn");
  const testConnectionBtn = document.getElementById("test-connection-btn");
  const loadingDiv = document.getElementById("loading");
  const errorMessage = document.getElementById("error-message");
  const successMessage = document.getElementById("success-message");
  const connectionDetails = document.getElementById("connection-details");
  const connectionInfo = document.getElementById("connection-info");

  // Test connection button
  testConnectionBtn.addEventListener("click", async () => {
    // Hide previous messages
    errorMessage.classList.add("hidden");
    successMessage.classList.add("hidden");
    connectionDetails.classList.add("hidden");

    // Show loading
    loadingDiv.classList.remove("hidden");
    loadingDiv.querySelector("p").textContent = "Testing connection, please wait...";
    testConnectionBtn.disabled = true;

    // Get form data
    const formData = {
      server: document.getElementById("server").value.trim(),
      username: document.getElementById("username").value,
      password: document.getElementById("password").value,
    };

    try {
      // Send request to test connection API
      const response = await fetch("/api/test-connection", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      // Check if response is JSON
      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        // Handle non-JSON response (likely HTML error page)
        const textResponse = await response.text();
        throw new Error("Server returned non-JSON response. There might be an internal server error.");
      }

      const data = await response.json();

      // Display connection details
      connectionDetails.classList.remove("hidden");

      if (response.ok && data.success) {
        // Show success message
        successMessage.textContent = "Connection successful! You can now analyze AD accounts.";
        successMessage.classList.remove("hidden");

        // Show connection details
        let baseDNsHtml = "";
        if (data.details.available_base_dns && data.details.available_base_dns.length > 0) {
          baseDNsHtml = "<p><strong>Available Base DNs:</strong></p><ul>";
          data.details.available_base_dns.forEach((dn) => {
            baseDNsHtml += `<li>${dn}${dn === data.details.default_base_dn ? " (default)" : ""}</li>`;
          });
          baseDNsHtml += "</ul>";
        }

        connectionInfo.innerHTML = `
          <p><strong>Network connectivity:</strong> ✅ Success</p>
          <p><strong>Authentication:</strong> ✅ Success</p>
          <p><strong>Server:</strong> ${formData.server}</p>
          <p><strong>Username:</strong> ${formData.username}</p>
          ${baseDNsHtml}
        `;
      } else {
        // Show error message
        errorMessage.textContent = data.error || "Failed to connect to AD server.";
        errorMessage.classList.remove("hidden");

        // Show connection details
        connectionInfo.innerHTML = `
          <p><strong>Network connectivity:</strong> ${data.details?.network_connectivity ? "✅ Success" : "❌ Failed"}</p>
          <p><strong>Authentication:</strong> ${data.details?.authentication ? "✅ Success" : "❌ Failed"}</p>
          <p><strong>Server:</strong> ${formData.server}</p>
          <p><strong>Username:</strong> ${formData.username}</p>
          <p><strong>Error:</strong> ${data.error || "Unknown error"}</p>
        `;
      }
    } catch (error) {
      console.error("Error:", error);
      errorMessage.textContent = "An error occurred while testing the connection: " + error.message;
      errorMessage.classList.remove("hidden");

      // Show connection details
      connectionInfo.innerHTML = `
        <p><strong>Error:</strong> ${error.message || "Unknown error"}</p>
      `;
      connectionDetails.classList.remove("hidden");
    } finally {
      // Hide loading
      loadingDiv.classList.add("hidden");
      testConnectionBtn.disabled = false;
    }
  });

  // Main form submission
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    // Show loading and hide error
    loadingDiv.classList.remove("hidden");
    loadingDiv.querySelector("p").textContent = "Analyzing accounts, please wait...";
    errorMessage.classList.add("hidden");
    successMessage.classList.add("hidden");
    connectionDetails.classList.add("hidden");
    analyzeBtn.disabled = true;

    // Get form data
    const formData = {
      server: document.getElementById("server").value.trim(),
      username: document.getElementById("username").value,
      password: document.getElementById("password").value,
      base_dn: document.getElementById("base-dn").value || "",
      debug: document.getElementById("debug-mode").checked,
    };

    try {
      // Send request to API
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(formData),
      });

      // Check if response is JSON
      const contentType = response.headers.get("content-type");
      if (!contentType || !contentType.includes("application/json")) {
        // Handle non-JSON response (likely HTML error page)
        const textResponse = await response.text();
        throw new Error("Server returned non-JSON response. There might be an internal server error.");
      }

      const data = await response.json();

      if (response.ok && data.success) {
        // Store credentials in session storage (except password)
        sessionStorage.setItem("server", formData.server);
        sessionStorage.setItem("username", formData.username);
        sessionStorage.setItem("base_dn", formData.base_dn);

        // Redirect to results page
        window.location.href = "/results";
      } else {
        // Show detailed error message
        const errorText = data.error || "Failed to analyze AD accounts. Please check your connection details.";

        errorMessage.textContent = errorText;
        errorMessage.classList.remove("hidden");
        console.error("Analysis error:", data.error);

        // Show connection details if we have them
        if (data.details) {
          connectionDetails.classList.remove("hidden");

          let baseDNsHtml = "";
          if (data.details.available_base_dns && data.details.available_base_dns.length > 0) {
            baseDNsHtml = "<p><strong>Available Base DNs:</strong></p><ul>";
            data.details.available_base_dns.forEach((dn) => {
              baseDNsHtml += `<li>${dn}${dn === data.details.default_base_dn ? " (default)" : ""}</li>`;
            });
            baseDNsHtml += "</ul>";
          }

          let suggestionsHtml = "";
          if (data.details.suggestions && data.details.suggestions.length > 0) {
            suggestionsHtml = "<p><strong>Suggestions:</strong></p><ul>";
            data.details.suggestions.forEach((suggestion) => {
              suggestionsHtml += `<li>${suggestion}</li>`;
            });
            suggestionsHtml += "</ul>";
          }

          connectionInfo.innerHTML = `
            <p><strong>Error:</strong> ${data.error || "Unknown error"}</p>
            ${baseDNsHtml}
            ${suggestionsHtml}
          `;
        }
      }
    } catch (error) {
      console.error("Error:", error);
      errorMessage.textContent =
        "An error occurred. Please check your connection details and try again: " + error.message;
      errorMessage.classList.remove("hidden");
    } finally {
      // Hide loading
      loadingDiv.classList.add("hidden");
      analyzeBtn.disabled = false;
    }
  });
});