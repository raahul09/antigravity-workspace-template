// GrootTrade Client Dashboard Logic

document.addEventListener("DOMContentLoaded", () => {
    // State management
    const state = {
        activeTab: "dashboard",
        botRunning: false,
        tgConnected: false,
        tgAuthorized: false,
        mt5Connected: false,
        allChatsFetched: [],
        logIntervalId: null,
        statusIntervalId: null
    };

    // DOM Elements
    const menuItems = document.querySelectorAll(".menu-item");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const pageTitle = document.getElementById("page-title");
    const pageSubtitle = document.getElementById("page-subtitle");
    
    // Status indicators
    const tgPill = document.getElementById("tg-pill");
    const mt5Pill = document.getElementById("mt5-pill");
    const tgStatusVal = document.getElementById("tg-status-val");
    const tgUserVal = document.getElementById("tg-user-val");
    const mt5StatusVal = document.getElementById("mt5-status-val");
    const mt5AccountVal = document.getElementById("mt5-account-val");
    const botStatusVal = document.getElementById("bot-status-val");
    const botStatusDesc = document.getElementById("bot-status-desc");

    // Controls
    const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
    const consoleStartBtn = document.getElementById("console-start-btn");
    const consoleStopBtn = document.getElementById("console-stop-btn");
    const consoleRestartBtn = document.getElementById("console-restart-btn");
    const monitoredSourcesSummary = document.getElementById("monitored-sources-summary");

    // Tester Tab
    const testSignalTextarea = document.getElementById("test-signal-textarea");
    const runTestBtn = document.getElementById("run-test-btn");
    const clearTestBtn = document.getElementById("clear-test-btn");
    const testPlaceholder = document.getElementById("test-output-placeholder");
    const testSuccess = document.getElementById("test-output-success");
    const testFail = document.getElementById("test-output-fail");
    const jsonOutput = document.getElementById("json-output");

    // Config Tab
    const configForm = document.getElementById("config-form");
    const refreshChatsBtn = document.getElementById("refresh-chats-btn");
    const chatsSelectionList = document.getElementById("chats-selection-list");
    const saveStatusMsg = document.getElementById("save-status-msg");

    // Logs Tab
    const logTerminal = document.getElementById("log-terminal");
    const refreshLogsBtn = document.getElementById("refresh-logs-btn");
    const logAutoscroll = document.getElementById("log-autoscroll");

    // 1. Tab Navigation Routing
    const tabDetails = {
        dashboard: {
            title: "Dashboard",
            subtitle: "Real-time status overview and performance controls"
        },
        tester: {
            title: "Signal Tester",
            subtitle: "Test and parse raw trading signal formatting"
        },
        config: {
            title: "Settings Configuration",
            subtitle: "Edit credentials, risk levels, parsing triggers, and source channels"
        },
        logs: {
            title: "System Logs",
            subtitle: "Monitor active background events and runtime execution"
        }
    };

    function switchTab(tabId) {
        state.activeTab = tabId;
        
        // Update menu active class
        menuItems.forEach(item => {
            if (item.getAttribute("data-tab") === tabId) {
                item.classList.add("active");
            } else {
                item.classList.remove("active");
            }
        });

        // Update tab contents visibility
        tabPanes.forEach(pane => {
            if (pane.id === `${tabId}-tab`) {
                pane.classList.add("active");
            } else {
                pane.classList.remove("active");
            }
        });

        // Update titles
        const details = tabDetails[tabId];
        if (details) {
            pageTitle.innerText = details.title;
            pageSubtitle.innerText = details.subtitle;
        }

        // Context-specific actions
        if (tabId === "logs") {
            fetchLogs();
            startLogPolling();
        } else {
            stopLogPolling();
        }

        if (tabId === "config") {
            fetchConfig();
        }
    }

    menuItems.forEach(item => {
        item.addEventListener("click", () => {
            switchTab(item.getAttribute("data-tab"));
        });
    });

    // 2. Fetch and Update Status
    async function updateStatus() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();

            state.botRunning = data.bot_running;
            state.tgConnected = data.telegram.connected;
            state.tgAuthorized = data.telegram.authorized;
            state.mt5Connected = data.mt5.connected;

            // Render Telegram status
            const tgIndicator = tgPill.querySelector(".status-indicator");
            const tgText = tgPill.querySelector("span:last-child");
            if (state.tgAuthorized) {
                tgIndicator.className = "status-indicator active";
                tgText.innerText = "Telegram: Connected";
                tgStatusVal.innerText = "Authorized";
                tgStatusVal.style.color = "var(--color-success)";
                tgUserVal.innerText = data.telegram.user || "Unknown User";
            } else if (state.tgConnected) {
                tgIndicator.className = "status-indicator idle";
                tgText.innerText = "Telegram: Waiting Code";
                tgStatusVal.innerText = "Connected (Need Auth)";
                tgStatusVal.style.color = "var(--color-warning)";
                tgUserVal.innerText = "Awaiting credentials / code";
            } else {
                tgIndicator.className = "status-indicator inactive";
                tgText.innerText = "Telegram: Disconnected";
                tgStatusVal.innerText = "Disconnected";
                tgStatusVal.style.color = "var(--color-danger)";
                tgUserVal.innerText = "Configure API details in Settings";
            }

            // Render MT5 status
            const mt5Indicator = mt5Pill.querySelector(".status-indicator");
            const mt5Text = mt5Pill.querySelector("span:last-child");
            if (state.mt5Connected) {
                mt5Indicator.className = "status-indicator active";
                mt5Text.innerText = "MT5: Connected";
                mt5StatusVal.innerText = "Connected";
                mt5StatusVal.style.color = "var(--color-success)";
                mt5AccountVal.innerText = `Account: ${data.mt5.account} (${data.mt5.broker})`;
            } else {
                mt5Indicator.className = "status-indicator inactive";
                mt5Text.innerText = "MT5: Disconnected";
                mt5StatusVal.innerText = "Disconnected";
                mt5StatusVal.style.color = "var(--color-danger)";
                mt5AccountVal.innerText = "No active broker session";
            }

            // Render overall Bot Running controls
            if (state.botRunning) {
                botStatusVal.innerText = "Running";
                botStatusVal.style.color = "var(--color-success)";
                botStatusDesc.innerText = "Actively monitoring channels";
                
                // Sidebar button state
                sidebarToggleBtn.className = "btn btn-danger stop-btn";
                sidebarToggleBtn.innerHTML = '<i class="fa-solid fa-stop"></i> Stop Bot';

                // Console Buttons state
                consoleStartBtn.disabled = true;
                consoleStopBtn.disabled = false;
                consoleRestartBtn.disabled = false;
            } else {
                botStatusVal.innerText = "Inactive";
                botStatusVal.style.color = "var(--text-muted)";
                botStatusDesc.innerText = "Bot execution task stopped";

                // Sidebar button state
                sidebarToggleBtn.className = "btn btn-primary start-btn";
                sidebarToggleBtn.innerHTML = '<i class="fa-solid fa-play"></i> Start Bot';

                // Console Buttons state
                consoleStartBtn.disabled = false;
                consoleStopBtn.disabled = true;
                consoleRestartBtn.disabled = true;
            }
        } catch (err) {
            console.error("Error updating status:", err);
        }
    }

    // 3. Engine Control Handlers
    async function controlBot(action) {
        try {
            sidebarToggleBtn.disabled = true;
            consoleStartBtn.disabled = true;
            consoleStopBtn.disabled = true;
            consoleRestartBtn.disabled = true;

            const res = await fetch("/api/control", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action })
            });
            const data = await res.json();
            
            await updateStatus();
            
            // Reload channels selection list to verify session
            if (state.activeTab === "config") {
                fetchTelegramChats();
            }
        } catch (err) {
            console.error(`Error executing bot action ${action}:`, err);
        } finally {
            sidebarToggleBtn.disabled = false;
        }
    }

    sidebarToggleBtn.addEventListener("click", () => {
        const action = state.botRunning ? "stop" : "start";
        controlBot(action);
    });

    consoleStartBtn.addEventListener("click", () => controlBot("start"));
    consoleStopBtn.addEventListener("click", () => controlBot("stop"));
    consoleRestartBtn.addEventListener("click", () => controlBot("restart"));

    // 4. Load Configuration settings
    let isConfigLoaded = false;
    async function fetchConfig() {
        if (isConfigLoaded) return; // Load only once on tab open, unless refreshed
        
        try {
            const res = await fetch("/api/config");
            const config = await res.json();

            // Populate form elements
            for (const key in config) {
                const element = document.getElementById(key);
                if (element) {
                    if (element.type === "checkbox") {
                        element.checked = config[key];
                    } else {
                        element.value = config[key];
                    }
                }
            }

            // Render source channels summary in Dashboard
            renderSourcesSummary(config.telegram_source_chat);

            isConfigLoaded = true;
            
            // Fetch chats selection details
            await fetchTelegramChats();
        } catch (err) {
            console.error("Error loading configurations:", err);
        }
    }

    function renderSourcesSummary(sourceChatStr) {
        if (!sourceChatStr || !sourceChatStr.trim()) {
            monitoredSourcesSummary.innerHTML = `<p class="empty-text">No active channels configured. Bot is monitoring ALL direct messages.</p>`;
            return;
        }

        const sources = sourceChatStr.split(",").map(s => s.trim()).filter(Boolean);
        monitoredSourcesSummary.innerHTML = "";
        
        sources.forEach(source => {
            const div = document.createElement("div");
            div.className = "source-item";
            div.innerHTML = `<i class="fa-solid fa-square-rss"></i> <span>${source}</span>`;
            monitoredSourcesSummary.appendChild(div);
        });
    }

    // 5. Fetch available Telegram dialogs for selection
    async function fetchTelegramChats() {
        chatsSelectionList.innerHTML = `<div class="loading-chats"><i class="fa-solid fa-spinner fa-spin"></i> Fetching channels from active Telegram session...</div>`;
        
        try {
            const res = await fetch("/api/telegram/chats");
            const data = await res.json();

            if (!data.success) {
                chatsSelectionList.innerHTML = `<div class="loading-chats" style="color: var(--color-danger)"><i class="fa-solid fa-circle-exclamation"></i> ${data.message}</div>`;
                return;
            }

            state.allChatsFetched = data.chats;
            renderChatsCheckboxes();
        } catch (err) {
            chatsSelectionList.innerHTML = `<div class="loading-chats" style="color: var(--color-danger)"><i class="fa-solid fa-circle-exclamation"></i> API error: failed to retrieve channels.</div>`;
        }
    }

    function renderChatsCheckboxes() {
        const configuredSourcesStr = document.getElementById("telegram_source_chat").value || "";
        const configuredSources = configuredSourcesStr.split(",").map(s => s.trim()).filter(Boolean);

        if (state.allChatsFetched.length === 0) {
            chatsSelectionList.innerHTML = `<p class="empty-text">No channels found in this account.</p>`;
            return;
        }

        chatsSelectionList.innerHTML = "";
        
        state.allChatsFetched.forEach(chat => {
            const isSelected = configuredSources.includes(chat.id) || configuredSources.includes(chat.title);
            
            const label = document.createElement("label");
            label.className = `chat-checkbox-label ${isSelected ? "selected" : ""}`;
            
            // Set type icon
            let typeIcon = '<i class="fa-solid fa-user chat-icon"></i>';
            if (chat.type === "Channel") {
                typeIcon = '<i class="fa-solid fa-bullhorn chat-icon"></i>';
            } else if (chat.type === "Group") {
                typeIcon = '<i class="fa-solid fa-users chat-icon"></i>';
            }

            label.innerHTML = `
                <input type="checkbox" value="${chat.id}" ${isSelected ? "checked" : ""}>
                ${typeIcon}
                <span>${chat.title}</span>
            `;

            // Append listener to update styling and compile value list on change
            const checkbox = label.querySelector("input");
            checkbox.addEventListener("change", () => {
                if (checkbox.checked) {
                    label.classList.add("selected");
                } else {
                    label.classList.remove("selected");
                }
                updateSelectedSourcesInput();
            });

            chatsSelectionList.appendChild(label);
        });
    }

    function updateSelectedSourcesInput() {
        const checkboxes = chatsSelectionList.querySelectorAll("input[type='checkbox']:checked");
        const values = Array.from(checkboxes).map(cb => cb.value);
        document.getElementById("telegram_source_chat").value = values.join(", ");
    }

    refreshChatsBtn.addEventListener("click", fetchTelegramChats);

    // 6. Save configurations to backend
    configForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        saveStatusMsg.className = "save-status";
        saveStatusMsg.innerText = "Saving...";

        const payload = {};
        const elements = configForm.querySelectorAll("input");
        
        elements.forEach(element => {
            if (element.id) {
                if (element.type === "checkbox") {
                    payload[element.id] = element.checked;
                } else if (element.type === "number") {
                    payload[element.id] = element.value ? parseFloat(element.value) : null;
                } else {
                    payload[element.id] = element.value;
                }
            }
        });

        try {
            const res = await fetch("/api/config", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();

            if (data.success) {
                saveStatusMsg.className = "save-status success";
                saveStatusMsg.innerText = data.restarted ? "Configuration saved! Bot restarted successfully." : "Configuration saved!";
                
                // Render summary
                renderSourcesSummary(payload.telegram_source_chat);
                
                // Clear message after 4s
                setTimeout(() => {
                    saveStatusMsg.innerText = "";
                }, 4000);
            } else {
                saveStatusMsg.className = "save-status error";
                saveStatusMsg.innerText = `Save failed: ${data.detail || "Server error"}`;
            }
        } catch (err) {
            saveStatusMsg.className = "save-status error";
            saveStatusMsg.innerText = "Network error. Failed to save configuration.";
        }
    });

    // 7. Signal parsing testing
    runTestBtn.addEventListener("click", async () => {
        const text = testSignalTextarea.value.trim();
        if (!text) return;

        runTestBtn.disabled = true;
        runTestBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Parsing...';

        try {
            const res = await fetch("/api/parser/test", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ text })
            });
            const data = await res.json();

            testPlaceholder.classList.add("hidden");

            if (data.success && data.signal) {
                testSuccess.classList.remove("hidden");
                testFail.classList.add("hidden");
                jsonOutput.innerText = JSON.stringify(data.signal, null, 2);
            } else {
                testSuccess.classList.add("hidden");
                testFail.classList.remove("hidden");
                const errParagraph = testFail.querySelector("p");
                if (data.error) {
                    errParagraph.innerText = `Error compiling message: ${data.error}`;
                } else {
                    errParagraph.innerText = "Regex pattern did not match this format. The Stop Loss (SL) or trade action was not detected. Verify keyword settings.";
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            runTestBtn.disabled = false;
            runTestBtn.innerHTML = '<i class="fa-solid fa-circle-check"></i> Parse Signal';
        }
    });

    clearTestBtn.addEventListener("click", () => {
        testSignalTextarea.value = "";
        testPlaceholder.classList.remove("hidden");
        testSuccess.classList.add("hidden");
        testFail.classList.add("hidden");
        jsonOutput.innerText = "";
    });

    // 8. Log polling terminal rendering
    async function fetchLogs() {
        try {
            const res = await fetch("/api/logs");
            const data = await res.json();

            if (data.success) {
                const logsList = data.logs || [];
                logTerminal.textContent = logsList.join("\n");
                
                if (logAutoscroll.checked) {
                    logTerminal.scrollTop = logTerminal.scrollHeight;
                }
            }
        } catch (err) {
            console.error("Error fetching logs:", err);
        }
    }

    refreshLogsBtn.addEventListener("click", fetchLogs);

    function startLogPolling() {
        if (!state.logIntervalId) {
            fetchLogs();
            state.logIntervalId = setInterval(fetchLogs, 3000);
        }
    }

    function stopLogPolling() {
        if (state.logIntervalId) {
            clearInterval(state.logIntervalId);
            state.logIntervalId = null;
        }
    }

    function startStatusPolling() {
        updateStatus();
        state.statusIntervalId = setInterval(updateStatus, 3000);
    }

    // Initialize application
    startStatusPolling();
});
