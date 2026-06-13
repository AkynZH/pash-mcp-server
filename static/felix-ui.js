// felix-ui.js
// Управление параллельными SSE-стримами от Qwen Code и Felix Agent

const QWEN_STREAM_URL = '/api/qwen_stream';
const FELIX_STREAM_URL = '/api/agent_stream';
const MAX_EVENTS = 50; // Ограничение количества отображаемых событий для предотвращения переполнения DOM

let qwenEventSource = null;
let felixEventSource = null;

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    logSystem('Инициализация UI...');
    connectQwenStream();
    connectFelixStream();
    checkHealth();
});

function connectQwenStream() {
    updateStatus('status-qwen', 'Подключение...', 'status-warn');
    qwenEventSource = new EventSource(QWEN_STREAM_URL);

    qwenEventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            appendEvent('qwen-log', data, 'qwen');
        } catch (e) {
            console.warn('Ошибка парсинга Qwen события:', e, event.data);
        }
    };

    qwenEventSource.onerror = (err) => {
        updateStatus('status-qwen', 'Разорвано (Reconnecting...)', 'status-err');
        logSystem(`Qwen SSE ошибка/переподключение. Код: ${err.target.readyState}`);
        // EventSource автоматически попытается переподключиться
    };

    qwenEventSource.onopen = () => {
        updateStatus('status-qwen', 'Подключено', 'status-ok');
        logSystem('Qwen SSE соединение установлено.');
    };
}

function connectFelixStream() {
    updateStatus('status-felix', 'Подключение...', 'status-warn');
    felixEventSource = new EventSource(FELIX_STREAM_URL);

    felixEventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            appendEvent('felix-log', data, 'felix');
        } catch (e) {
            console.warn('Ошибка парсинга Felix события:', e, event.data);
        }
    };

    felixEventSource.onerror = (err) => {
        updateStatus('status-felix', 'Разорвано (Reconnecting...)', 'status-err');
        logSystem(`Felix SSE ошибка/переподключение. Код: ${err.target.readyState}`);
    };

    felixEventSource.onopen = () => {
        updateStatus('status-felix', 'Подключено', 'status-ok');
        logSystem('Felix SSE соединение установлено.');
    };
}

function appendEvent(elementId, data, type) {
    const container = document.getElementById(elementId);
    if (!container) return;

    // Пропускаем keepalive (пустые сообщения или только ":")
    if (!data || (typeof data === 'object' && Object.keys(data).length === 0)) {
        return;
    }

    const eventDiv = document.createElement('div');
    eventDiv.className = `event-item ${type}`;
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'event-time';
    const timestamp = data.timestamp ? new Date(data.timestamp * 1000).toLocaleTimeString() : new Date().toLocaleTimeString();
    timeDiv.textContent = `[${timestamp}] ${data.type || 'event'}`;
    
    const dataDiv = document.createElement('div');
    dataDiv.className = 'event-data';
    dataDiv.textContent = JSON.stringify(data, null, 2);

    eventDiv.appendChild(timeDiv);
    eventDiv.appendChild(dataDiv);
    container.appendChild(eventDiv);

    // Ограничение количества элементов
    while (container.children.length > MAX_EVENTS) {
        container.removeChild(container.firstChild);
    }

    // Автопрокрутка вниз
    container.scrollTop = container.scrollHeight;
}

function updateStatus(elementId, text, className) {
    const el = document.getElementById(elementId);
    if (el) {
        el.textContent = text;
        el.className = `status-value ${className}`;
    }
}

function logSystem(message) {
    const container = document.getElementById('system-log');
    if (!container) return;

    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    
    container.appendChild(entry);
    while (container.children.length > 30) {
        container.removeChild(container.firstChild);
    }
    container.scrollTop = container.scrollHeight;
}

async function sendCommand(target) {
    const input = document.getElementById('command-input');
    const payloadText = input.value.trim();
    if (!payloadText) {
        logSystem('Ошибка: Пустой ввод.');
        return;
    }

    let payload;
    try {
        // Пытаемся распарсить как JSON, если не получается, оборачиваем в строку
        payload = JSON.parse(payloadText);
    } catch (e) {
        payload = { message: payloadText };
    }

    const endpoint = target === 'felix' ? '/api/push_felix' : '/api/push_qwen';
    
    logSystem(`Отправка команды в ${target.toUpperCase()}...`);
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        logSystem(`Успех: ${result.message}`);
        input.value = ''; // Очистка поля ввода
    } catch (error) {
        logSystem(`Ошибка отправки: ${error.message}`);
    }
}

async function checkHealth() {
    try {
        const response = await fetch('/api/health');
        const data = await response.json();
        logSystem(`Health check: Qwen queue: ${data.qwen_queue_size}, Felix queue: ${data.felix_queue_size}`);
    } catch (e) {
        logSystem(`Health check failed: ${e.message}`);
    }
    // Повторная проверка каждые 10 секунд
    setTimeout(checkHealth, 10000);
}

function clearZone(elementId) {
    const container = document.getElementById(elementId);
    if (container) {
        container.innerHTML = '';
        logSystem(`Журнал ${elementId} очищен.`);
    }
}

// Глобальная очистка при закрытии страницы
window.addEventListener('beforeunload', () => {
    if (qwenEventSource) qwenEventSource.close();
    if (felixEventSource) felixEventSource.close();
});
