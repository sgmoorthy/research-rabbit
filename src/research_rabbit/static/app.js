document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons
    lucide.createIcons();

    // DOM Elements
    const navButtons = document.querySelectorAll('.nav-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const providerSelect = document.getElementById('settings-provider');
    const groupOllamaModel = document.getElementById('group-ollama-model');
    const groupCustomModel = document.getElementById('group-custom-model');
    const groupGeminiKey = document.getElementById('group-gemini-key');
    const groupOpenaiKey = document.getElementById('group-openai-key');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const saveAlert = document.getElementById('save-alert');

    const topicInput = document.getElementById('topic-input');
    const startBtn = document.getElementById('start-btn');
    const livePanel = document.getElementById('live-panel');
    const resultPanel = document.getElementById('result-panel');
    const timelineContainer = document.getElementById('timeline-container');
    const loopCurrentSpan = document.getElementById('loop-current');
    const loopMaxSpan = document.getElementById('loop-max');
    const resultTopicTitle = document.getElementById('result-topic-title');
    const markdownOutput = document.getElementById('markdown-output');
    const downloadMdBtn = document.getElementById('download-md-btn');
    const clearResultBtn = document.getElementById('clear-result-btn');

    const historyList = document.getElementById('history-list');

    // Modal Elements
    const reportModal = document.getElementById('report-modal');
    const modalReportTitle = document.getElementById('modal-report-title');
    const modalReportContent = document.getElementById('modal-report-content');
    const modalDownloadBtn = document.getElementById('modal-download-btn');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const closeModalBtn = document.getElementById('close-modal-btn');

    // State Variables
    let currentTaskEventSource = null;
    let currentReportData = null;
    let modalReportData = null;

    // --- Tab Switching Logic ---
    navButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.getAttribute('data-tab');
            
            navButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const targetPane = document.getElementById(targetTab);
            if (targetPane) {
                targetPane.classList.add('active');
            }

            if (targetTab === 'tab-history') {
                loadHistory();
            }
        });
    });

    // --- Password visibility toggle ---
    document.querySelectorAll('.toggle-password-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const input = btn.previousElementSibling;
            if (input.type === 'password') {
                input.type = 'text';
                btn.innerHTML = '<i data-lucide="eye-off"></i>';
            } else {
                input.type = 'password';
                btn.innerHTML = '<i data-lucide="eye"></i>';
            }
            lucide.createIcons();
        });
    });

    // --- Settings UI Adjustments based on LLM Provider ---
    providerSelect.addEventListener('change', () => {
        adjustSettingsForm(providerSelect.value);
    });

    function adjustSettingsForm(provider) {
        if (provider === 'ollama') {
            groupOllamaModel.classList.remove('hidden');
            groupCustomModel.classList.add('hidden');
            groupGeminiKey.classList.add('hidden');
            groupOpenaiKey.classList.add('hidden');
        } else if (provider === 'gemini') {
            groupOllamaModel.classList.add('hidden');
            groupCustomModel.classList.remove('hidden');
            groupGeminiKey.classList.remove('hidden');
            groupOpenaiKey.classList.add('hidden');
        } else if (provider === 'openai') {
            groupOllamaModel.classList.add('hidden');
            groupCustomModel.classList.remove('hidden');
            groupGeminiKey.classList.add('hidden');
            groupOpenaiKey.classList.remove('hidden');
        }
    }

    // --- Load Settings ---
    async function loadSettings() {
        try {
            const response = await fetch('/api/settings');
            const settings = await response.json();
            
            providerSelect.value = settings.llm_provider || 'ollama';
            document.getElementById('settings-local-llm').value = settings.local_llm || 'llama3.2';
            document.getElementById('settings-model-name').value = settings.model_name || '';
            document.getElementById('settings-tavily-key').value = settings.tavily_api_key || '';
            document.getElementById('settings-gemini-key').value = settings.gemini_api_key || '';
            document.getElementById('settings-openai-key').value = settings.openai_api_key || '';
            document.getElementById('settings-max-loops').value = settings.max_loops || 3;

            adjustSettingsForm(settings.llm_provider || 'ollama');
        } catch (error) {
            console.error('Error loading settings:', error);
        }
    }

    // --- Save Settings ---
    saveSettingsBtn.addEventListener('click', async () => {
        const settings = {
            llm_provider: providerSelect.value,
            local_llm: document.getElementById('settings-local-llm').value,
            model_name: document.getElementById('settings-model-name').value,
            tavily_api_key: document.getElementById('settings-tavily-key').value,
            gemini_api_key: document.getElementById('settings-gemini-key').value,
            openai_api_key: document.getElementById('settings-openai-key').value,
            max_loops: parseInt(document.getElementById('settings-max-loops').value, 10) || 3
        };

        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            if (response.ok) {
                saveAlert.classList.remove('hidden');
                setTimeout(() => saveAlert.classList.add('hidden'), 3000);
            } else {
                alert('Failed to save settings');
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            alert('Error connecting to server.');
        }
    });

    // --- Start Research ---
    startBtn.addEventListener('click', async () => {
        const topic = topicInput.value.trim();
        if (!topic) {
            alert('Please enter a research topic!');
            return;
        }

        // Disable UI
        startBtn.disabled = true;
        topicInput.disabled = true;
        startBtn.innerHTML = '<span>Processing...</span> <div class="pulse-icon"></div>';

        // Clear and show timeline panel
        timelineContainer.innerHTML = '';
        livePanel.classList.remove('hidden');
        resultPanel.classList.add('hidden');
        
        loopCurrentSpan.textContent = '0';
        const maxLoops = parseInt(document.getElementById('settings-max-loops').value, 10) || 3;
        loopMaxSpan.textContent = maxLoops;

        try {
            const response = await fetch('/api/research', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ research_topic: topic })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to start research task');
            }

            const data = await response.json();
            const taskId = data.task_id;
            connectToStream(taskId, topic);
        } catch (error) {
            console.error('Error starting research:', error);
            alert(`Error: ${error.message}`);
            resetSearchUI();
        }
    });

    // --- SSE Event Stream Handler ---
    function connectToStream(taskId, topic) {
        if (currentTaskEventSource) {
            currentTaskEventSource.close();
        }

        currentTaskEventSource = new EventSource(`/api/stream/${taskId}`);
        
        currentTaskEventSource.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            handleStreamEvent(payload, topic);
        };

        currentTaskEventSource.onerror = (err) => {
            console.error('EventSource error:', err);
            addTimelineItem('system_error', 'Connection Interrupted', 'The live connection to the server was lost. Checking server status...');
            currentTaskEventSource.close();
            resetSearchUI();
        };
    }

    function handleStreamEvent(payload, topic) {
        if (payload.type === 'step') {
            const node = payload.node;
            const data = payload.data;

            // Render different details based on graph nodes
            if (node === 'generate_query') {
                const searchQ = data.search_query || '';
                addTimelineItem(
                    node,
                    'Generating Search Query 🔍',
                    `Formulating initial search parameters for topic...\nQuery: "${searchQ}"`,
                    searchQ
                );
            } else if (node === 'web_research') {
                const results = data.web_research_results ? data.web_research_results[0] : '';
                const loops = data.research_loop_count || 0;
                loopCurrentSpan.textContent = loops;
                addTimelineItem(
                    node,
                    'Searching Web & Gathering Sources 🌐',
                    `Query executed successfully. Sources retrieved & deduplicated.`,
                    results
                );
            } else if (node === 'summarize_sources') {
                const summary = data.running_summary || '';
                addTimelineItem(
                    node,
                    'Synthesizing & Drafting Summary 📝',
                    `Incorporated web content into working draft. Summary extended.`,
                    summary
                );
            } else if (node === 'reflect_on_summary') {
                const nextQ = data.search_query || '';
                addTimelineItem(
                    node,
                    'Critique & Knowledge Gap Identification 🔄',
                    `Reflected on current knowledge draft, located missing angles.\nNext Query: "${nextQ}"`,
                    nextQ
                );
            } else if (node === 'finalize_summary') {
                addTimelineItem(
                    node,
                    'Finalizing Report & Citations 🏁',
                    'Assembled bibliography references and completed final polishing.',
                    data.running_summary
                );
            }
        } 
        else if (payload.type === 'done') {
            currentTaskEventSource.close();
            currentReportData = payload.data;
            displayFinalReport(topic, currentReportData.summary);
            resetSearchUI();
        } 
        else if (payload.type === 'error') {
            currentTaskEventSource.close();
            addTimelineItem(
                'error',
                'Execution Error ❌',
                `The research agent encountered an error: ${payload.message}\n\nTraceback:\n${payload.traceback}`
            );
            resetSearchUI();
        }
    }

    // --- Timeline Render Helper ---
    function addTimelineItem(nodeType, title, description, codeDetails = null) {
        // Remove active state from previous items
        const activeItems = timelineContainer.querySelectorAll('.timeline-item.active');
        activeItems.forEach(item => {
            item.classList.remove('active');
            item.classList.add('completed');
            const dot = item.querySelector('.timeline-dot i');
            if (dot) {
                dot.setAttribute('data-lucide', 'check');
            }
        });

        const item = document.createElement('div');
        item.className = `timeline-item active ${nodeType === 'error' || nodeType === 'system_error' ? 'failed' : ''}`;
        
        let iconName = 'play';
        if (nodeType === 'generate_query' || nodeType === 'reflect_on_summary') iconName = 'search';
        else if (nodeType === 'web_research') iconName = 'globe';
        else if (nodeType === 'summarize_sources') iconName = 'edit-3';
        else if (nodeType === 'finalize_summary') iconName = 'check-circle';
        else if (nodeType === 'error' || nodeType === 'system_error') iconName = 'alert-triangle';

        let codeHtml = '';
        if (codeDetails) {
            codeHtml = `
                <div class="timeline-expandable">
                    <pre><code>${escapeHtml(codeDetails)}</code></pre>
                </div>
            `;
        }

        item.innerHTML = `
            <div class="timeline-dot">
                <i data-lucide="${iconName}"></i>
            </div>
            <div class="timeline-content">
                <div class="timeline-title">${title}</div>
                <div class="timeline-details">${description.replace(/\n/g, '<br>')}</div>
                ${codeHtml}
            </div>
        `;

        timelineContainer.appendChild(item);
        lucide.createIcons();
        
        // Scroll content to the latest step
        item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function resetSearchUI() {
        startBtn.disabled = false;
        topicInput.disabled = false;
        startBtn.innerHTML = '<span>Analyze</span> <i data-lucide="arrow-right"></i>';
        lucide.createIcons();
    }

    // --- Final Report Render ---
    function displayFinalReport(topic, summaryMarkdown) {
        resultTopicTitle.textContent = `Analysis: ${topic}`;
        markdownOutput.innerHTML = marked.parse(summaryMarkdown);
        resultPanel.classList.remove('hidden');
        resultPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // --- Clear Search & Results ---
    clearResultBtn.addEventListener('click', () => {
        resultPanel.classList.add('hidden');
        livePanel.classList.add('hidden');
        topicInput.value = '';
        currentReportData = null;
    });

    // --- Export Markdown ---
    downloadMdBtn.addEventListener('click', () => {
        if (!currentReportData) return;
        downloadReportFile(currentReportData.topic, currentReportData.summary);
    });

    function downloadReportFile(topic, markdownContent) {
        const filename = `${topic.toLowerCase().replace(/[^a-z0-9]+/g, '-')}-research.md`;
        const blob = new Blob([markdownContent], { type: 'text/markdown;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    // --- Load History List ---
    async function loadHistory() {
        historyList.innerHTML = '<div class="no-data"><div class="pulse-icon"></div><span>Loading history...</span></div>';
        try {
            const response = await fetch('/api/reports');
            const reports = await response.json();
            
            if (reports.length === 0) {
                historyList.innerHTML = `
                    <div class="no-data">
                        <i data-lucide="inbox"></i>
                        <p>No past research files found.</p>
                    </div>
                `;
                lucide.createIcons();
                return;
            }

            historyList.innerHTML = '';
            reports.forEach(report => {
                const date = new Date(report.timestamp).toLocaleString();
                const card = document.createElement('div');
                card.className = 'history-card';
                card.innerHTML = `
                    <div class="history-card-header">
                        <h4>${escapeHtml(report.topic)}</h4>
                        <div class="history-meta">
                            <i data-lucide="calendar" style="width: 12px; height: 12px;"></i>
                            <span>${date}</span>
                        </div>
                    </div>
                    <div class="history-footer">
                        <span class="history-badge">${report.llm_provider}</span>
                        <button class="history-delete-btn" data-id="${report.id}" title="Delete Report">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </div>
                `;

                // Card Click opens Modal
                card.addEventListener('click', (e) => {
                    // Prevent modal opening when deleting
                    if (e.target.closest('.history-delete-btn')) return;
                    openReportModal(report.id);
                });

                // Delete Button handler
                const delBtn = card.querySelector('.history-delete-btn');
                delBtn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm(`Are you sure you want to delete the report on "${report.topic}"?`)) {
                        await deleteReport(report.id);
                    }
                });

                historyList.appendChild(card);
            });
            lucide.createIcons();
        } catch (error) {
            console.error('Error loading history:', error);
            historyList.innerHTML = '<div class="no-data"><span class="text-danger">Failed to load history list.</span></div>';
        }
    }

    // --- Delete Report ---
    async function deleteReport(reportId) {
        try {
            const response = await fetch(`/api/reports/${reportId}`, {
                method: 'DELETE'
            });
            if (response.ok) {
                loadHistory();
            } else {
                alert('Failed to delete report.');
            }
        } catch (error) {
            console.error('Error deleting report:', error);
        }
    }

    // --- Open Report Modal ---
    async function openReportModal(reportId) {
        try {
            modalReportContent.innerHTML = '<div class="no-data"><div class="pulse-icon"></div><span>Loading report content...</span></div>';
            reportModal.classList.remove('hidden');

            const response = await fetch(`/api/reports/${reportId}`);
            if (!response.ok) throw new Error('Report could not be retrieved.');

            modalReportData = await response.json();
            modalReportTitle.textContent = `Report: ${modalReportData.topic}`;
            modalReportContent.innerHTML = marked.parse(modalReportData.summary);
            lucide.createIcons();
        } catch (error) {
            console.error('Error opening report modal:', error);
            modalReportContent.innerHTML = `<div class="no-data"><span class="text-danger">Error: ${error.message}</span></div>`;
        }
    }

    // --- Close Modal ---
    function closeModal() {
        reportModal.classList.add('hidden');
        modalReportData = null;
    }

    modalCloseBtn.addEventListener('click', closeModal);
    closeModalBtn.addEventListener('click', closeModal);
    reportModal.addEventListener('click', (e) => {
        if (e.target === reportModal) closeModal();
    });

    // --- Download from Modal ---
    modalDownloadBtn.addEventListener('click', () => {
        if (!modalReportData) return;
        downloadReportFile(modalReportData.topic, modalReportData.summary);
    });

    // Initial load
    loadSettings();
});
