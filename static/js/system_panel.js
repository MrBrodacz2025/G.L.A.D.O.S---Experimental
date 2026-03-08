// Global variables for charts
let cpuChart, memoryChart, diskChart, networkChart;
let historyData = {
    cpu: [],
    memory: [],
    disk: { read: [], write: [] },
    network: { sent: [], recv: [] },
    timestamps: []
};
const MAX_HISTORY = 60; // 60 data points
let currentPath = '/home'; // Current file browser path

// Navigation
document.querySelectorAll('.sidebar-item').forEach(item => {
    item.addEventListener('click', () => {
        const tabName = item.getAttribute('data-tab');
        
        document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
        
        item.classList.add('active');
        document.getElementById(tabName).classList.add('active');
        
        loadTabData(tabName);
    });
});

function loadTabData(tabName) {
    switch(tabName) {
        case 'overview':
            loadOverview();
            break;
        case 'stats':
            initCharts();
            startHistoryCollection();
            break;
        case 'processes':
            loadProcesses();
            break;
        case 'storage':
            loadDiskInfo();
            break;
        case 'network':
            loadNetworkInfo();
            break;
        case 'services':
            loadServices();
            break;
        case 'logs':
            loadLogs();
            break;
        case 'files':
            loadFiles(currentPath);
            break;

    }
}

function getProgressClass(percentage) {
    if (percentage >= 90) return 'danger';
    if (percentage >= 75) return 'warning';
    return '';
}

// Overview Functions
async function loadOverview() {
    try {
        const [info, cpu, memory, disk] = await Promise.all([
            fetch('/api/system/info').then(r => r.json()),
            fetch('/api/system/cpu').then(r => r.json()),
            fetch('/api/system/memory').then(r => r.json()),
            fetch('/api/system/disk').then(r => r.json())
        ]);

        // Update header
        document.getElementById('header-hostname').textContent = info.hostname || 'System Panel';

        // System Status with Processor Details
        let cpuHtml = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; font-size: 1.2rem;">Procesor</h3>
                ${cpu.temperature ? `<span style="font-size: 1.2rem; color: ${cpu.temperature > 70 ? '#ff3b30' : '#34c759'};">${cpu.temperature}°C</span>` : ''}
            </div>
            <div class="info-row">
                <span class="info-label">${cpu.total_cores} ${cpu.total_cores === 1 ? 'procesor' : cpu.total_cores < 5 ? 'procesory' : 'procesorów'}</span>
                <span class="info-value">średnio: ${cpu.cpu_usage_total.toFixed(0)}% maks: ${Math.max(...cpu.cpu_usage_per_core).toFixed(0)}%</span>
            </div>
            <div class="progress-bar" style="margin-top: 0.5rem;">
                <div class="progress-fill ${getProgressClass(cpu.cpu_usage_total)}" style="width: ${cpu.cpu_usage_total}%"></div>
            </div>
        `;
        
        if (cpu.load_average) {
            cpuHtml += `
                <div class="info-row" style="margin-top: 1rem;">
                    <span class="info-label">Obciążenie</span>
                    <span class="info-value">1 minuta: ${cpu.load_average['1min']}, 5 minut: ${cpu.load_average['5min']}, 15 minut: ${cpu.load_average['15min']}</span>
                </div>
            `;
        }
        
        if (cpu.top_processes && cpu.top_processes.length > 0) {
            cpuHtml += `<div style="margin-top: 1rem;"><strong style="color: #9aa3d6;">Usługi:</strong></div>`;
            cpu.top_processes.forEach(proc => {
                cpuHtml += `
                    <div class="info-row">
                        <span class="info-label">${proc.name}</span>
                        <span class="info-value" style="color: ${proc.cpu_percent > 50 ? '#ff3b30' : proc.cpu_percent > 20 ? '#ff9500' : '#34c759'};">${proc.cpu_percent}%</span>
                    </div>
                `;
            });
        }
        
        document.getElementById('system-status').innerHTML = cpuHtml;

        // System Usage
        const avgDiskUsage = disk.partitions.length > 0 
            ? disk.partitions.reduce((sum, p) => sum + p.percentage, 0) / disk.partitions.length 
            : 0;

        document.getElementById('system-usage').innerHTML = `
            <div class="info-row">
                <span class="info-label">CPU</span>
                <span class="info-value">${cpu.cpu_usage_total.toFixed(1)}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill ${getProgressClass(cpu.cpu_usage_total)}" 
                     style="width: ${cpu.cpu_usage_total}%"></div>
            </div>
            
            <div class="info-row" style="margin-top: 1rem;">
                <span class="info-label">Pamięć</span>
                <span class="info-value">${memory.percentage.toFixed(1)}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill ${getProgressClass(memory.percentage)}" 
                     style="width: ${memory.percentage}%"></div>
            </div>

            <div class="info-row" style="margin-top: 1rem;">
                <span class="info-label">Dysk</span>
                <span class="info-value">${avgDiskUsage.toFixed(1)}%</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill ${getProgressClass(avgDiskUsage)}" 
                     style="width: ${avgDiskUsage}%"></div>
            </div>
        `;

        // System Info
        document.getElementById('system-info').innerHTML = `
            <div class="info-row">
                <span class="info-label">Nazwa hosta</span>
                <span class="info-value">${info.hostname}</span>
            </div>
            <div class="info-row">
                <span class="info-label">System operacyjny</span>
                <span class="info-value">${info.system}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Wersja</span>
                <span class="info-value">${info.release}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Architektura</span>
                <span class="info-value">${info.machine}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Uptime</span>
                <span class="info-value">${info.uptime}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Czas uruchomienia</span>
                <span class="info-value">${info.boot_time}</span>
            </div>
        `;

        // System Config
        document.getElementById('system-config').innerHTML = `
            <div class="info-row">
                <span class="info-label">Procesor</span>
                <span class="info-value">${info.processor}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Rdzenie</span>
                <span class="info-value">${cpu.physical_cores} fizyczne, ${cpu.total_cores} logiczne</span>
            </div>
            <div class="info-row">
                <span class="info-label">Pamięć RAM</span>
                <span class="info-value">${memory.total}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Dostępna pamięć</span>
                <span class="info-value">${memory.available}</span>
            </div>
        `;

    } catch (error) {
        console.error('Error loading overview:', error);
    }
}

// Charts initialization
function initCharts() {
    if (cpuChart) return; // Already initialized

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { 
                display: false,
                labels: { color: '#a8b5ff' }
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: { 
                    color: 'rgba(255, 255, 255, 0.05)',
                    borderColor: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: { color: '#9aa3d6' }
            },
            x: {
                grid: { 
                    color: 'rgba(255, 255, 255, 0.05)',
                    borderColor: 'rgba(255, 255, 255, 0.1)'
                },
                ticks: { color: '#9aa3d6' }
            }
        }
    };

    // CPU Chart
    const cpuCtx = document.getElementById('cpuChart').getContext('2d');
    cpuChart = new Chart(cpuCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Użycie CPU (%)',
                data: [],
                borderColor: '#5d85ff',
                backgroundColor: 'rgba(93, 133, 255, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: chartOptions
    });

    // Memory Chart
    const memCtx = document.getElementById('memoryChart').getContext('2d');
    memoryChart = new Chart(memCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Użycie pamięci (%)',
                data: [],
                borderColor: '#34c759',
                backgroundColor: 'rgba(52, 199, 89, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: chartOptions
    });

    // Disk IO Chart
    const diskCtx = document.getElementById('diskChart').getContext('2d');
    diskChart = new Chart(diskCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Odczyt',
                    data: [],
                    borderColor: '#ff9500',
                    backgroundColor: 'rgba(255, 149, 0, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Zapis',
                    data: [],
                    borderColor: '#ff3b30',
                    backgroundColor: 'rgba(255, 59, 48, 0.1)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: { ...chartOptions, plugins: { legend: { display: true, labels: { color: '#a8b5ff' } } } }
    });

    // Network Chart
    const netCtx = document.getElementById('networkChart').getContext('2d');
    networkChart = new Chart(netCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Wysłane',
                    data: [],
                    borderColor: '#5d85ff',
                    backgroundColor: 'rgba(93, 133, 255, 0.1)',
                    fill: true,
                    tension: 0.4
                },
                {
                    label: 'Odebrane',
                    data: [],
                    borderColor: '#a855f7',
                    backgroundColor: 'rgba(168, 85, 247, 0.1)',
                    fill: true,
                    tension: 0.4
                }
            ]
        },
        options: { ...chartOptions, plugins: { legend: { display: true, labels: { color: '#a8b5ff' } } } }
    });
}

let historyInterval;
let lastDiskIO = { read: 0, write: 0 };
let lastNetIO = { sent: 0, recv: 0 };

async function startHistoryCollection() {
    if (historyInterval) clearInterval(historyInterval);
    
    async function collectData() {
        try {
            const [cpu, memory, disk] = await Promise.all([
                fetch('/api/system/cpu').then(r => r.json()),
                fetch('/api/system/memory').then(r => r.json()),
                fetch('/api/system/disk').then(r => r.json())
            ]);

            const now = new Date().toLocaleTimeString();
            
            // Add data
            historyData.cpu.push(cpu.cpu_usage_total);
            historyData.memory.push(memory.percentage);
            historyData.timestamps.push(now);

            // Disk IO (calculate delta)
            const currentDiskRead = disk.io.read_count || 0;
            const currentDiskWrite = disk.io.write_count || 0;
            const diskReadDelta = Math.max(0, currentDiskRead - lastDiskIO.read);
            const diskWriteDelta = Math.max(0, currentDiskWrite - lastDiskIO.write);
            historyData.disk.read.push(diskReadDelta);
            historyData.disk.write.push(diskWriteDelta);
            lastDiskIO = { read: currentDiskRead, write: currentDiskWrite };

            // Network IO (would need implementation)
            historyData.network.sent.push(Math.random() * 100); // Placeholder
            historyData.network.recv.push(Math.random() * 100); // Placeholder

            // Limit history
            if (historyData.timestamps.length > MAX_HISTORY) {
                historyData.cpu.shift();
                historyData.memory.shift();
                historyData.disk.read.shift();
                historyData.disk.write.shift();
                historyData.network.sent.shift();
                historyData.network.recv.shift();
                historyData.timestamps.shift();
            }

            // Update charts
            updateCharts();

            // Update current values
            document.getElementById('cpu-current').textContent = cpu.cpu_usage_total.toFixed(1) + '%';
            document.getElementById('mem-current').textContent = memory.percentage.toFixed(1) + '%';
            const avgDisk = disk.partitions.reduce((sum, p) => sum + p.percentage, 0) / disk.partitions.length;
            document.getElementById('disk-current').textContent = avgDisk.toFixed(1) + '%';

        } catch (error) {
            console.error('Error collecting history:', error);
        }
    }

    collectData();
    historyInterval = setInterval(collectData, 2000);
}

function updateCharts() {
    if (!cpuChart) return;

    cpuChart.data.labels = historyData.timestamps;
    cpuChart.data.datasets[0].data = historyData.cpu;
    cpuChart.update('none');

    memoryChart.data.labels = historyData.timestamps;
    memoryChart.data.datasets[0].data = historyData.memory;
    memoryChart.update('none');

    diskChart.data.labels = historyData.timestamps;
    diskChart.data.datasets[0].data = historyData.disk.read;
    diskChart.data.datasets[1].data = historyData.disk.write;
    diskChart.update('none');

    networkChart.data.labels = historyData.timestamps;
    networkChart.data.datasets[0].data = historyData.network.sent;
    networkChart.data.datasets[1].data = historyData.network.recv;
    networkChart.update('none');
}

// Processes
async function loadProcesses() {
    try {
        const response = await fetch('/api/system/processes');
        const data = await response.json();
        
        if (data.processes.length === 0) {
            document.getElementById('processes-info').innerHTML = '<p>Brak procesów do wyświetlenia</p>';
            return;
        }

        const tableHTML = `
            <table>
                <thead>
                    <tr>
                        <th>PID</th>
                        <th>Nazwa</th>
                        <th>Użytkownik</th>
                        <th>CPU %</th>
                        <th>RAM %</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.processes.map(proc => `
                        <tr>
                            <td>${proc.pid}</td>
                            <td>${proc.name}</td>
                            <td>${proc.username}</td>
                            <td>${(proc.cpu_percent || 0).toFixed(1)}%</td>
                            <td>${proc.memory_percent.toFixed(1)}%</td>
                            <td>
                                <span class="status-badge status-${proc.status === 'running' ? 'running' : 'sleeping'}">
                                    ${proc.status}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        document.getElementById('processes-info').innerHTML = tableHTML;
    } catch (error) {
        document.getElementById('processes-info').innerHTML = `
            <div class="error">Błąd ładowania danych: ${error.message}</div>
        `;
    }
}

// Disk Info
async function loadDiskInfo() {
    try {
        const response = await fetch('/api/system/disk');
        const data = await response.json();
        
        const partitionsHTML = data.partitions.map(p => `
            <div style="margin-bottom: 1.5rem;">
                <div class="info-row">
                    <span class="info-label">${p.device} - ${p.mountpoint}</span>
                    <span class="info-value">${p.percentage.toFixed(1)}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill ${getProgressClass(p.percentage)}" 
                         style="width: ${p.percentage}%"></div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 0.5rem; font-size: 0.85rem; color: #999;">
                    <span>Użyte: ${p.used}</span>
                    <span>Wolne: ${p.free}</span>
                    <span>Całkowite: ${p.total}</span>
                </div>
            </div>
        `).join('');

        document.getElementById('disk-info').innerHTML = partitionsHTML;
    } catch (error) {
        document.getElementById('disk-info').innerHTML = `
            <div class="error">Błąd ładowania danych: ${error.message}</div>
        `;
    }
}

// Network Info
async function loadNetworkInfo() {
    try {
        const response = await fetch('/api/system/network');
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('network-info').innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }
        
        if (!data.interfaces || data.interfaces.length === 0) {
            document.getElementById('network-info').innerHTML = '<p>Brak dostępnych interfejsów sieciowych</p>';
            return;
        }

        const tableHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Interfejs</th>
                        <th>Adres IP</th>
                        <th>Maska</th>
                        <th>Status</th>
                        <th>Wysłane</th>
                        <th>Odebrane</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.interfaces.map(iface => `
                        <tr>
                            <td><strong>${iface.interface}</strong></td>
                            <td>${iface.ip}</td>
                            <td>${iface.netmask || 'N/A'}</td>
                            <td>
                                <span class="status-badge ${iface.is_up ? 'status-running' : 'status-stopped'}">
                                    ${iface.is_up ? 'Aktywny' : 'Nieaktywny'}
                                </span>
                            </td>
                            <td>${iface.bytes_sent}</td>
                            <td>${iface.bytes_recv}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        document.getElementById('network-info').innerHTML = tableHTML;
    } catch (error) {
        document.getElementById('network-info').innerHTML = `
            <div class="error">Błąd ładowania danych: ${error.message}</div>
        `;
    }
}

// Services
async function loadServices() {
    try {
        const response = await fetch('/api/system/services');
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('services-info').innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }
        
        if (data.message) {
            document.getElementById('services-info').innerHTML = `<p>${data.message}</p>`;
            return;
        }

        if (!data.services || data.services.length === 0) {
            document.getElementById('services-info').innerHTML = '<p>Brak usług do wyświetlenia</p>';
            return;
        }

        const tableHTML = `
            <table>
                <thead>
                    <tr>
                        <th>Usługa</th>
                        <th>Opis</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.services.map(service => `
                        <tr>
                            <td><strong>${service.unit || 'N/A'}</strong></td>
                            <td>${service.description || 'N/A'}</td>
                            <td>
                                <span class="status-badge ${service.active === 'active' ? 'status-running' : 'status-stopped'}">
                                    ${service.active || 'N/A'}
                                </span>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        document.getElementById('services-info').innerHTML = tableHTML;
    } catch (error) {
        document.getElementById('services-info').innerHTML = `
            <div class="error">Błąd ładowania danych: ${error.message}</div>
        `;
    }
}

// Logs
async function loadLogs() {
    try {
        const response = await fetch('/api/system/logs');
        const data = await response.json();
        
        if (data.error) {
            document.getElementById('logs-info').innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }
        
        if (data.message) {
            document.getElementById('logs-info').innerHTML = `<p>${data.message}</p>`;
            return;
        }

        if (!data.logs || data.logs.length === 0) {
            document.getElementById('logs-info').innerHTML = '<p>Brak logów do wyświetlenia</p>';
            return;
        }

        const logsHTML = data.logs.map(log => {
            return `
                <div style="padding: 0.75rem; background: rgba(93, 133, 255, 0.05); margin-bottom: 0.5rem; border-radius: 8px; border-left: 3px solid #5d85ff; font-family: 'Courier New', monospace; font-size: 0.85rem; color: #ddd;">
                    ${log.message || JSON.stringify(log)}
                </div>
            `;
        }).join('');

        document.getElementById('logs-info').innerHTML = logsHTML;
    } catch (error) {
        document.getElementById('logs-info').innerHTML = `
            <div class="error">Błąd ładowania danych: ${error.message}</div>
        `;
    }
}

// Terminal Functions
function addTerminalLine(text, className = '') {
    const output = document.getElementById('terminal-output');
    const line = document.createElement('div');
    line.className = 'terminal-line ' + className;
    line.textContent = text;
    output.appendChild(line);
    output.scrollTop = output.scrollHeight;
}

async function executeCommand() {
    const input = document.getElementById('terminal-input');
    const command = input.value.trim();
    
    if (!command) return;

    addTerminalLine('$ ' + command, 'terminal-prompt');
    input.value = '';

    try {
        const response = await fetch('/api/terminal/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });

        const data = await response.json();

        if (response.ok) {
            if (data.stdout) {
                data.stdout.split('\n').forEach(line => {
                    if (line) addTerminalLine(line);
                });
            }
            if (data.stderr) {
                data.stderr.split('\n').forEach(line => {
                    if (line) addTerminalLine(line, 'terminal-error');
                });
            }
            if (data.returncode !== 0) {
                addTerminalLine(`Command exited with code ${data.returncode}`, 'terminal-error');
            }
        } else {
            addTerminalLine('Error: ' + (data.error || 'Unknown error'), 'terminal-error');
        }
    } catch (error) {
        addTerminalLine('Error: ' + error.message, 'terminal-error');
    }

    addTerminalLine('---');
}

function clearTerminal() {
    document.getElementById('terminal-output').innerHTML = `
        <div class="terminal-line">Terminal wyczyszczony</div>
        <div class="terminal-line">---</div>
    `;
}

// File Browser
let currentEditingFile = null;
let codeMirrorEditor = null;

async function loadFiles(path) {
    currentPath = path || currentPath;
    const container = document.getElementById('files-list');
    container.innerHTML = '<div class="loading">Ładowanie...</div>';
    
    try {
        const response = await fetch(`/api/files/browse?path=${encodeURIComponent(currentPath)}`);
        const data = await response.json();
        
        document.getElementById('current-path').textContent = data.current_path || currentPath;
        
        if (data.error) {
            container.innerHTML = `<div class="error">${data.error}</div>`;
            return;
        }
        
        let html = '<div class="file-grid">';
        
        // Parent directory link
        if (data.parent_path) {
            html += `
                <div class="file-item directory" onclick="loadFiles('${data.parent_path}')">
                    <span class="material-icons">arrow_upward</span>
                    <div class="file-name">..</div>
                    <div class="file-meta">Powrót</div>
                </div>
            `;
        }
        
        // Directories first
        const dirs = data.files.filter(f => f.is_dir === true);
        const files = data.files.filter(f => f.is_dir !== true);
        
        dirs.forEach(file => {
            const safePath = file.path.replace(/'/g, "\\'");
            html += `
                <div class="file-item directory" onclick="loadFiles('${safePath}')">
                    <span class="material-icons">folder</span>
                    <div class="file-name">${file.name}</div>
                    <div class="file-meta">${file.modified}</div>
                </div>
            `;
        });
        
        // Then files
        files.forEach(file => {
            const safePath = file.path.replace(/'/g, "\\'");
            const isPython = file.name.endsWith('.py');
            const icon = isPython ? 'description' : 'insert_drive_file';
            const fileClass = isPython ? 'python-file' : '';
            const onclick = isPython ? `openFileEditor('${safePath}', '${file.name}')` : '';
            
            html += `
                <div class="file-item ${fileClass}" ${onclick ? `onclick="${onclick}"` : ''}>
                    <span class="material-icons">${icon}</span>
                    <div class="file-name">${file.name}</div>
                    <div class="file-meta">${file.size}</div>
                </div>
            `;
        });
        
        html += '</div>';
        
        if (data.files.length === 0) {
            html = '<div style="text-align: center; padding: 2rem; color: #9aa3d6;">Brak plików w tym katalogu</div>';
        }
        
        container.innerHTML = html;
    } catch (error) {
        container.innerHTML = `<div class="error">Błąd: ${error.message}</div>`;
    }
}

// File Editor
async function openFileEditor(filePath, fileName) {
    currentEditingFile = filePath;
    document.getElementById('editor-file-name').textContent = fileName;
    document.getElementById('file-editor-modal').classList.add('active');
    
    // Inicjalizuj CodeMirror jeśli jeszcze nie istnieje
    if (!codeMirrorEditor) {
        const wrapper = document.getElementById('code-editor-wrapper');
        codeMirrorEditor = CodeMirror(wrapper, {
            mode: 'python',
            theme: 'material-darker',
            lineNumbers: true,
            lineWrapping: false,
            autoCloseBrackets: true,
            matchBrackets: true,
            styleActiveLine: true,
            indentUnit: 4,
            indentWithTabs: false,
            viewportMargin: Infinity,
            extraKeys: {
                "Ctrl-Space": "autocomplete",
                "Ctrl-F": "findPersistent",
                "Ctrl-/": function(cm) {
                    cm.toggleComment();
                }
            },
            foldGutter: true,
            gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"]
        });
        
        // Event listener dla aktualizacji statystyk
        codeMirrorEditor.on('change', function(cm) {
            updateEditorStats(cm);
        });
        
        // Ustaw wysokość CodeMirror
        codeMirrorEditor.setSize('100%', '100%');
    }
    
    codeMirrorEditor.setValue('Ładowanie...');
    
    try {
        const response = await fetch(`/api/files/read?path=${encodeURIComponent(filePath)}`);
        const data = await response.json();
        
        if (data.error) {
            alert('Błąd: ' + data.error);
            closeFileEditor();
            return;
        }
        
        codeMirrorEditor.setValue(data.content);
        
        // Force refresh after setting content
        setTimeout(() => {
            codeMirrorEditor.refresh();
            codeMirrorEditor.scrollTo(0, 0);
        }, 100);
        
        updateEditorStats(codeMirrorEditor);
    } catch (error) {
        alert('Błąd: ' + error.message);
        closeFileEditor();
    }
}

function updateEditorStats(cm) {
    const lineCount = cm.lineCount();
    const content = cm.getValue();
    const sizeKB = (new Blob([content]).size / 1024).toFixed(2);
    
    document.getElementById('editor-lines').textContent = `${lineCount} ${lineCount === 1 ? 'linia' : lineCount < 5 ? 'linie' : 'linii'}`;
    document.getElementById('editor-size').textContent = `${sizeKB} KB`;
}

function closeFileEditor() {
    document.getElementById('file-editor-modal').classList.remove('active');
    currentEditingFile = null;
}

function formatCode() {
    if (!codeMirrorEditor) return;
    
    // Podstawowe formatowanie - wyrównanie wcięć
    const content = codeMirrorEditor.getValue();
    const lines = content.split('\n');
    let indentLevel = 0;
    const formatted = lines.map(line => {
        const trimmed = line.trim();
        
        // Zmniejsz wcięcie dla linii kończących blok
        if (trimmed.match(/^(return|break|continue|pass|raise|elif|else|except|finally)/)) {
            indentLevel = Math.max(0, indentLevel - 1);
        }
        
        const result = '    '.repeat(indentLevel) + trimmed;
        
        // Zwiększ wcięcie po liniach rozpoczynających blok
        if (trimmed.endsWith(':')) {
            indentLevel++;
        }
        
        return result;
    }).join('\n');
    
    codeMirrorEditor.setValue(formatted);
}

function undoEdit() {
    if (codeMirrorEditor) {
        codeMirrorEditor.undo();
    }
}

function redoEdit() {
    if (codeMirrorEditor) {
        codeMirrorEditor.redo();
    }
}

function searchInCode() {
    if (codeMirrorEditor) {
        codeMirrorEditor.execCommand('findPersistent');
    }
}

async function saveFile() {
    if (!currentEditingFile || !codeMirrorEditor) return;
    
    const content = codeMirrorEditor.getValue();
    
    try {
        const response = await fetch('/api/files/write', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                path: currentEditingFile,
                content: content
            })
        });
        
        const data = await response.json();
        
        if (data.error) {
            alert('Błąd: ' + data.error);
            return;
        }
        
        alert('✅ ' + data.message + '\nBackup: ' + data.backup);
        closeFileEditor();
        loadFiles(currentPath); // Refresh file list
    } catch (error) {
        alert('Błąd: ' + error.message);
    }
}

// Terminal input enter key
document.getElementById('terminal-input').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        executeCommand();
    }
});

// Auto-refresh overview every 5 seconds
setInterval(() => {
    const activeTab = document.querySelector('.tab-content.active');
    if (activeTab && activeTab.id === 'overview') {
        loadOverview();
    }
}, 5000);

// Initial load
loadOverview();
