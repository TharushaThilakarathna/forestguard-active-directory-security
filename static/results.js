document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const totalUsersEl = document.getElementById("total-users");
  const permanentUsersEl = document.getElementById("permanent-users");
  const temporaryUsersEl = document.getElementById("temporary-users");
  const inactiveTempUsersEl = document.getElementById("inactive-temp-users");
  const accountsTableBody = document.getElementById("accounts-tbody");
  const noAccountsDiv = document.getElementById("no-accounts");
  const searchInput = document.getElementById("search-input");
  const selectAllCheckbox = document.getElementById("select-all");
  const disableBtn = document.getElementById("disable-btn");
  const deleteBtn = document.getElementById("delete-btn");
  const modal = document.getElementById("modal");
  const modalTitle = document.getElementById("modal-title");
  const modalMessage = document.getElementById("modal-message");
  const modalConfirmBtn = document.getElementById("modal-confirm");
  const modalCancelBtn = document.getElementById("modal-cancel");
  const closeBtn = document.querySelector(".close-btn");

  // Chart
  let accountChart = null;

  // State
  let accounts = [];
  let selectedAccounts = [];
  let currentAction = null;
  let summaryData = {};

  // Fetch data and initialize
  async function initialize() {
    try {
      // Fetch accounts data
      const response = await fetch("/api/accounts");
      const data = await response.json();

      if (response.ok && data.success) {
        accounts = data.accounts;
        summaryData = data.summary;

        // Update summary
        updateSummary();

        // Render accounts table
        renderAccountsTable();

        // Initialize chart
        initializeChart();
      } else {
        showError("Failed to load accounts data");
      }
    } catch (error) {
      console.error("Error:", error);
      showError("An error occurred while loading data");
    }
  }

  // Update summary numbers
  function updateSummary() {
    totalUsersEl.textContent = summaryData.totalUsers || 0;
    permanentUsersEl.textContent = summaryData.permanentUsers || 0;
    temporaryUsersEl.textContent = summaryData.temporaryUsers || 0;
    inactiveTempUsersEl.textContent = summaryData.inactiveTempUsers || 0;
  }

  // Initialize chart
  function initializeChart() {
    const ctx = document.getElementById("account-chart").getContext("2d");

    const permanentUsers = summaryData.permanentUsers || 0;
    const activeTempUsers = (summaryData.temporaryUsers || 0) - (summaryData.inactiveTempUsers || 0);
    const inactiveTempUsers = summaryData.inactiveTempUsers || 0;

    accountChart = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Permanent", "Active Temporary", "Inactive Temporary"],
        datasets: [
          {
            data: [permanentUsers, activeTempUsers, inactiveTempUsers],
            backgroundColor: [
              "#4ade80", // green for permanent
              "#facc15", // yellow for active temporary
              "#f87171", // red for inactive temporary
            ],
            borderWidth: 1,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false,
          },
        },
      },
    });
  }

  // Render accounts table
  function renderAccountsTable() {
    // Clear table
    accountsTableBody.innerHTML = "";

    // Filter accounts based on search
    const searchTerm = searchInput.value.toLowerCase();
    const filteredAccounts = accounts.filter(
      (account) =>
        account.username.toLowerCase().includes(searchTerm) ||
        (account.description && account.description.toLowerCase().includes(searchTerm)),
    );

    // Show/hide no accounts message
    if (filteredAccounts.length === 0) {
      noAccountsDiv.classList.remove("hidden");
      accountsTableBody.parentElement.parentElement.classList.add("hidden");
    } else {
      noAccountsDiv.classList.add("hidden");
      accountsTableBody.parentElement.parentElement.classList.remove("hidden");

      // Render accounts
      filteredAccounts.forEach((account) => {
        const row = document.createElement("tr");

        row.innerHTML = `
          <td>
            <input type="checkbox" class="account-checkbox" data-id="${account.id}" 
              ${selectedAccounts.includes(account.id) ? "checked" : ""}>
          </td>
          <td>${account.username}</td>
          <td>${account.description || ""}</td>
          <td>${account.lastLogin || "Never"}</td>
          <td>${account.loginCount}</td>
          <td>${account.expiryDate || "N/A"}</td>
          <td><span class="badge badge-inactive">Inactive Temp</span></td>
        `;

        accountsTableBody.appendChild(row);
      });

      // Add event listeners to checkboxes
      document.querySelectorAll(".account-checkbox").forEach((checkbox) => {
        checkbox.addEventListener("change", function () {
          const accountId = this.getAttribute("data-id");

          if (this.checked) {
            if (!selectedAccounts.includes(accountId)) {
              selectedAccounts.push(accountId);
            }
          } else {
            const index = selectedAccounts.indexOf(accountId);
            if (index !== -1) {
              selectedAccounts.splice(index, 1);
            }
          }

          updateSelectAllCheckbox();
          updateActionButtons();
        });
      });

      // Update select all checkbox state
      updateSelectAllCheckbox();
    }

    // Update action buttons state
    updateActionButtons();
  }

  // Update select all checkbox state
  function updateSelectAllCheckbox() {
    const checkboxes = document.querySelectorAll(".account-checkbox");
    const checkedCount = document.querySelectorAll(".account-checkbox:checked").length;

    if (checkboxes.length > 0 && checkedCount === checkboxes.length) {
      selectAllCheckbox.checked = true;
      selectAllCheckbox.indeterminate = false;
    } else if (checkedCount === 0) {
      selectAllCheckbox.checked = false;
      selectAllCheckbox.indeterminate = false;
    } else {
      selectAllCheckbox.indeterminate = true;
    }
  }

  // Update action buttons state
  function updateActionButtons() {
    const hasSelection = selectedAccounts.length > 0;
    disableBtn.disabled = !hasSelection;
    deleteBtn.disabled = !hasSelection;
  }

  // Show error message
  function showError(message) {
    const errorDiv = document.createElement("div");
    errorDiv.className = "error";
    errorDiv.textContent = message;

    // Insert after header
    const header = document.querySelector(".card-header");
    header.parentNode.insertBefore(errorDiv, header.nextSibling);
  }

  // Show modal
  function showModal(title, message, action) {
    modalTitle.textContent = title;
    modalMessage.textContent = message;
    currentAction = action;
    modal.classList.remove("hidden");
  }

  // Hide modal
  function hideModal() {
    modal.classList.add("hidden");
    currentAction = null;
  }

  // Event listeners

  // Search input
  searchInput.addEventListener("input", renderAccountsTable);

  // Select all checkbox
  selectAllCheckbox.addEventListener("change", function () {
    const checkboxes = document.querySelectorAll(".account-checkbox");

    checkboxes.forEach((checkbox) => {
      checkbox.checked = this.checked;

      const accountId = checkbox.getAttribute("data-id");
      const index = selectedAccounts.indexOf(accountId);

      if (this.checked && index === -1) {
        selectedAccounts.push(accountId);
      } else if (!this.checked && index !== -1) {
        selectedAccounts.splice(index, 1);
      }
    });

    updateActionButtons();
  });

  // Disable button
  disableBtn.addEventListener("click", () => {
    showModal("Disable Accounts", `Are you sure you want to disable ${selectedAccounts.length} account(s)?`, "disable");
  });

  // Delete button
  deleteBtn.addEventListener("click", () => {
    showModal(
      "Delete Accounts",
      `Are you sure you want to delete ${selectedAccounts.length} account(s)? This action cannot be undone.`,
      "delete",
    );
  });

  // Modal confirm button
  modalConfirmBtn.addEventListener("click", async () => {
    if (currentAction === "disable") {
      await performAction("/api/disable");
    } else if (currentAction === "delete") {
      await performAction("/api/delete");
    }

    hideModal();
  });

  // Modal cancel button and close button
  modalCancelBtn.addEventListener("click", hideModal);
  closeBtn.addEventListener("click", hideModal);

  // Perform action (disable or delete)
  async function performAction(endpoint) {
    try {
      // Get credentials from session storage or prompt user
      const credentials = {
        server: sessionStorage.getItem("server"),
        username: sessionStorage.getItem("username"),
        password: prompt("Enter password for authentication:"),
        base_dn: sessionStorage.getItem("base_dn") || "DC=example,DC=com",
        accountIds: selectedAccounts,
      };

      if (!credentials.server || !credentials.username || !credentials.password) {
        alert("Missing credentials. Please return to the login page.");
        return;
      }

      // Send request
      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(credentials),
      });

      const data = await response.json();

      if (response.ok && data.success) {
        // Refresh data
        initialize();

        // Clear selection
        selectedAccounts = [];
        updateActionButtons();

        alert("Operation completed successfully");
      } else {
        alert(`Operation failed: ${data.error || "Unknown error"}`);
      }
    } catch (error) {
      console.error("Error:", error);
      alert("An error occurred while performing the operation");
    }
  }

  // Initialize on page load
  initialize();
});