/******************************************************************************
 * dashboard.js
 *
 * Tres Lunas Environmental Monitoring Dashboard
 *
 * Displays temperature, humidity, status, and diagnostic information from a
 * network of Raspberry Pi Pico W sensor nodes publishing to Adafruit IO.
 *
 * Responsibilities:
 *
 *   • Manage Adafruit IO credentials and local configuration
 *   • Download historical sensor data through the REST API
 *   • Subscribe to live MQTT updates
 *   • Parse Pico-generated JSON payloads
 *   • Apply calibration offsets and unit conversions
 *   • Display current conditions and historical charts
 *   • Export chart data as CSV
 *   • Display diagnostic and status information in tabular form
 *
 * Design Notes:
 *
 *   • All timestamps originate on the Pico and are considered authoritative.
 *     Adafruit 'created_at' timestamps are used only for API pagination.
 *
 *   • Sensor payload format:
 *
 *         {
 *             "reading": 23.7,
 *             "timestamp": "2026-07-15T18:42:31Z"
 *         }
 *
 *   • Diagnostic payloads may contain arbitrary fields and are rendered
 *     dynamically into spreadsheet-style tables.
 *
 *   • Charts are generated from binned historical data and updated using
 *     incoming MQTT messages.
 *
 * Project Philosophy:
 *
 *   • Readability over cleverness
 *   • Explicit control flow
 *   • Conservative error handling
 *   • Minimal dependencies
 *   • Long-term unattended operation
 *
 * Primary Hardware:
 *
 *   • Raspberry Pi Pico W
 *   • DHT22 temperature / humidity sensors
 *   • Adafruit IO (REST + MQTT)
 *
 * Author: Radha Venkat
 * Project: Tres Lunas Climate Network
 * Firmware series: v1.x
 ******************************************************************************/

/******************************************************************************
 * APPLICATION STATE
 ******************************************************************************/
let client = null;
let config = {};
let tempChart = null;
let humidityChart = null;
let latestAllData = null;

/******************************************************************************
 * CONFIGURATION
 ******************************************************************************/

/* The Pico publishes raw readings in:
 *   - degrees Celsius
 *   - percent relative humidity
 *
 * Calibration, labels, colors, and unit conversion live here.
 *
 */
const NODES = [
    {
        id: '1',
        suffix: '131A17',
        label: 'Sensor #1',
        color: '#0e77ff',
        tempOffsetC: 0.0,
        humidityOffset: -5.2,
    },
    {
        id: '2',
        suffix: '131A19',
        label: 'Sensor #2',
        color: '#14b8a6',
        tempOffsetC: 0.0,
        humidityOffset: 0.5,
    },
    {
        id: '3',
        suffix: '131A1B',
        label: 'Sensor #3',
        color: '#a855f7',
        tempOffsetC: 0.0,
        humidityOffset: 0.0,
    },
];

/* Change this to "C" to display Celsius.
 * The stored and transmitted data remain in Celsius regardless.
 */
const DISPLAY_TEMPERATURE_UNIT = 'F';

/* These keys correspond to the existing HTML element IDs:
 *
 * val-t1, val-h1
 * val-t2, val-h2
 * val-t3, val-h3
 */
const SENSOR_KEYS = ['t1', 'h1', 't2', 'h2', 't3', 'h3'];

/******************************************************************************
 * DOM REFERENCES
 ******************************************************************************/
const rangeSelect = document.getElementById('range-select');
const binSelect = document.getElementById('bin-select');
const downloadCsvBtn = document.getElementById('download-csv-btn');
const modalEl = document.getElementById('config-modal');
const statusEl = document.getElementById('status');
const saveBtn = document.getElementById('save-config-btn');
const disconnectBtn = document.getElementById('disconnect-btn');
const showStatusTableBtn = document.getElementById('show-status-table-btn');
const showLogTableBtn = document.getElementById('show-log-table-btn');
const statusTableContainer = document.getElementById('status-table-container');
const logTableContainer = document.getElementById('log-table-container');

/******************************************************************************
 * NODE AND FEED HELPERS
 ******************************************************************************/
function getNode(sensorKey) {
    const nodeId = sensorKey.slice(1);

    return NODES.find((node) => node.id === nodeId);
}

function getMeasurementType(sensorKey) {
    return sensorKey.startsWith('t') ? 't' : 'h';
}

/*
 * Feed keys inside the tres-lunas Adafruit IO group:
 *
 * 131a17-t
 * 131a17-h
 */
function getFeedKey(sensorKey) {
    const node = getNode(sensorKey);

    if (!node || !node.suffix) {
        return null;
    }

    const suffix = node.suffix.toLowerCase();

    const measurement = getMeasurementType(sensorKey);

    return `${suffix}-${measurement}`;
}

/*
 * REST path for a feed inside the tres-lunas group.
 */
function getRestApiPath(sensorKey) {
    const feedKey = getFeedKey(sensorKey);

    if (!feedKey) {
        return null;
    }

    return `groups/tres-lunas/feeds/${feedKey}`;
}

function getDiagnosticsApiPath(node) {
    if (!node || !node.suffix) {
        return null;
    }

    const feedKey = `${node.suffix.toLowerCase()}-diagnostics`;

    return `groups/tres-lunas/feeds/${feedKey}`;
}

/*
 * Adafruit's MQTT topic uses the composite group.feed key:
 * username/feeds/tres-lunas.131a17-t
 */
function getMqttTopic(sensorKey) {
    const feedKey = getFeedKey(sensorKey);

    if (!feedKey) {
        return null;
    }

    return `${config.username}/feeds/` + `tres-lunas.${feedKey}`;
}

/******************************************************************************
 * SENSOR PAYLOAD PARSING
 ******************************************************************************/

/*
 * Expected JSON:
 *
 * {
 *     "reading": 21.4,
 *     "timestamp": "2026-07-13T16:11:47Z"
 * }
 *
 * This function is used for both REST data and live MQTT data.
 */
function parseSensorPayload(payload) {
    try {
        const record = typeof payload === 'string' ? JSON.parse(payload) : payload;
        const reading = Number(record.reading);
        const timestamp = new Date(record.timestamp);

        if (!Number.isFinite(reading)) {
            console.warn('Invalid sensor reading:', record);
            return null;
        }

        if (Number.isNaN(timestamp.getTime())) {
            console.warn('Invalid sensor timestamp:', record);
            return null;
        }

        return {
            reading,
            timestamp,
        };
    } catch (error) {
        console.warn('Unable to parse sensor payload:', payload, error);
        return null;
    }
}

function parseDiagnosticsPayload(item) {
    try {
        const payload = typeof item.value === 'string' ? JSON.parse(item.value) : item.value;

        if (payload === null || typeof payload !== 'object' || Array.isArray(payload)) {
            return null;
        }

        const normalized = {};

        Object.entries(payload).forEach(([key, value]) => {
            normalized[canonicalFieldName(key)] = value;
        });

        return normalized;
    } catch (error) {
        console.warn('Unable to parse diagnostics payload:', item.value, error);

        return null;
    }
}

function getPayloadTimestamp(payload, item) {
    const timestampValue = payload.Timestamp ?? payload.timestamp ?? item.created_at;

    const timestamp = new Date(timestampValue);

    if (Number.isNaN(timestamp.getTime())) {
        return null;
    }

    return timestamp;
}

function canonicalFieldName(name) {
    const lower = name.toLowerCase();

    const aliases = {
        type: 'Type',
        timestamp: 'Timestamp',
        bootcount: 'BootCount',
        subsystemcode: 'SubsystemCode',
        exceptype: 'ExcepType',
        message: 'Message',
        location: 'Location',
        rssi: 'RSSI',
        rssi_dbm: 'RSSI',
        uptime_s: 'Uptime_s',
        freememory: 'FreeMemory',
    };

    return aliases[lower] ?? prettyColumnName(name);
}

/******************************************************************************
 * CALIBRATION AND UNIT CONVERSION
 ******************************************************************************/

function convertTemperatureCelsius(temperatureC) {
    if (DISPLAY_TEMPERATURE_UNIT === 'F') {
        return (temperatureC * 9) / 5 + 32;
    }

    return temperatureC;
}

function getDisplayReading(sensorKey, rawReading) {
    const node = getNode(sensorKey);

    if (!node) {
        return rawReading;
    }

    if (sensorKey.startsWith('t')) {
        const calibratedC = rawReading + node.tempOffsetC;

        return convertTemperatureCelsius(calibratedC);
    }

    return rawReading + node.humidityOffset;
}

function getTemperatureUnitLabel() {
    return DISPLAY_TEMPERATURE_UNIT === 'F' ? '°F' : '°C';
}

function updateTemperatureUnitLabels() {
    const unitLabel = getTemperatureUnitLabel();

    ['t1', 't2', 't3'].forEach((sensorKey) => {
        const valueElement = document.getElementById(`val-${sensorKey}`);

        /*
         * The unit span immediately follows
         * the value span in the current HTML.
         */
        if (valueElement && valueElement.nextElementSibling) {
            valueElement.nextElementSibling.innerText = unitLabel;
        }
    });

    if (tempChart) {
        tempChart.options.scales.y.title.text = `Temperature (${unitLabel})`;

        tempChart.update('none');
    }
}

/******************************************************************************
 * INITIALIZATION AND CREDENTIALS
 ******************************************************************************/
function init() {
    const saved = localStorage.getItem('mqtt_dht11_config');

    if (saved) {
        config = JSON.parse(saved);

        modalEl.classList.add('hidden');

        disconnectBtn.classList.remove('hidden');

        buildCharts();
        updateTemperatureUnitLabels();
        loadHistoricalData();
    } else {
        modalEl.classList.remove('hidden');

        statusEl.innerText = 'Setup Required';

        statusEl.className =
            'px-3 py-1 rounded-full ' + 'text-xs font-semibold ' + 'bg-slate-700 text-slate-300';
    }
}

/******************************************************************************
 * CHART CREATION
 ******************************************************************************/

function chartOptions(yAxisTitle) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,

        scales: {
            x: {
                type: 'time',

                time: {
                    unit: 'hour',
                },

                grid: {
                    color: '#334155',
                },

                ticks: {
                    color: '#94a3b8',
                },
            },

            y: {
                title: {
                    display: true,
                    text: yAxisTitle,
                    color: '#94a3b8',
                },

                grid: {
                    color: '#334155',
                },

                ticks: {
                    color: '#94a3b8',
                },
            },
        },

        plugins: {
            legend: {
                labels: {
                    color: '#f8fafc',

                    font: {
                        size: 10,
                    },
                },
            },
        },

        elements: {
            point: {
                radius: 1,
                hoverRadius: 4,
            },

            line: {
                borderWidth: 2,
            },
        },
    };
}

function buildCharts() {
    if (tempChart) {
        tempChart.destroy();
    }

    if (humidityChart) {
        humidityChart.destroy();
    }

    tempChart = new Chart(document.getElementById('tempChart'), {
        type: 'line',

        data: {
            datasets: NODES.map((node) => ({
                label: node.label,

                data: [],

                borderColor: node.color,

                backgroundColor: `${node.color}22`,
            })),
        },

        options: chartOptions(`Temperature (` + `${getTemperatureUnitLabel()})`),
    });

    humidityChart = new Chart(document.getElementById('humidityChart'), {
        type: 'line',

        data: {
            datasets: NODES.map((node) => ({
                label: node.label,

                data: [],

                borderColor: node.color,

                backgroundColor: `${node.color}22`,
            })),
        },

        options: chartOptions('Relative humidity (%)'),
    });
}
/******************************************************************************
 * HISTORICAL DATA RETRIEVAL
 ******************************************************************************/

async function loadHistoricalData() {
    statusEl.innerText = 'Loading history...';

    try {
        const hours = Number.parseInt(rangeSelect.value, 10);

        /*
         * Approximate expected record count.
         * Current production interval may differ.
         */
        const targetCount = Math.ceil((hours * 60) / 5) + 100;

        const requests = SENSOR_KEYS.map((sensorKey) => {
            const apiPath = getRestApiPath(sensorKey);

            /*
             * A node with no configured suffix
             * simply contributes an empty dataset.
             */
            if (!apiPath) {
                return Promise.resolve([]);
            }

            return fetchFeedData(apiPath, hours, targetCount);
        });

        const allData = await Promise.all(requests);

        latestAllData = allData;

        updateChartsFromData(allData);
        updateCurrentCards(allData);
        connectLiveMqtt();
    } catch (error) {
        console.error('Historical data error:', error);

        statusEl.innerText = 'API Error';

        statusEl.className =
            'px-3 py-1 rounded-full ' + 'text-xs font-semibold ' + 'bg-rose-600 text-white';
    }
}

async function fetchFeedData(apiPath, hours = 168, targetCount = 2500) {
    let allPoints = [];
    let endTime = null;

    while (allPoints.length < targetCount) {
        let url =
            `https://io.adafruit.com/` +
            `api/v2/${config.username}/` +
            `${apiPath}/data?limit=1000`;

        if (endTime) {
            url += `&end_time=` + encodeURIComponent(endTime);
        } else {
            url += `&hours=${hours}`;
        }

        const response = await fetch(url, {
            headers: {
                'X-AIO-Key': config.apiKey,
            },
        });

        /*
         * Missing feeds should not prevent
         * the rest of the dashboard loading.
         */
        if (response.status === 404) {
            console.warn('Feed not found:', apiPath);

            return [];
        }

        if (!response.ok) {
            throw new Error(`${apiPath}: HTTP ` + `${response.status}`);
        }

        const page = await response.json();

        if (!Array.isArray(page) || page.length === 0) {
            break;
        }

        allPoints = allPoints.concat(page);

        if (page.length < 1000) {
            break;
        }

        /*
         * Keep using Adafruit's created_at
         * timestamp for API pagination.
         *
         * The embedded Pico timestamp is used
         * for plotting and display.
         */
        const oldestPoint = page[page.length - 1];

        const oldestMs = new Date(oldestPoint.created_at).getTime();

        endTime = new Date(oldestMs - 1000).toISOString();
    }

    return allPoints;
}

/******************************************************************************
 * CHART DATA PARSING AND BINNING
 ******************************************************************************/

function parseChartData(singleFeedArray, sensorKey, binMinutes = 60) {
    if (!Array.isArray(singleFeedArray)) {
        return [];
    }

    const rangeHours = Number.parseInt(rangeSelect.value, 10);

    const cutoffMs = Date.now() - rangeHours * 60 * 60 * 1000;

    const binMs = binMinutes * 60 * 1000;

    const bins = new Map();

    singleFeedArray.forEach((item) => {
        const record = parseSensorPayload(item.value);

        if (!record) {
            return;
        }

        const timestampMs = record.timestamp.getTime();

        if (timestampMs < cutoffMs) {
            return;
        }

        const reading = getDisplayReading(sensorKey, record.reading);

        if (!Number.isFinite(reading)) {
            return;
        }

        const binStart = Math.floor(timestampMs / binMs) * binMs;

        if (!bins.has(binStart)) {
            bins.set(binStart, {
                sum: 0,
                count: 0,
            });
        }

        const bin = bins.get(binStart);

        bin.sum += reading;
        bin.count += 1;
    });

    return Array.from(bins.entries())
        .map(([binStart, bin]) => ({
            x: new Date(Number(binStart)),

            y: bin.sum / bin.count,
        }))
        .sort((a, b) => a.x - b.x);
}

function updateChartsFromData(allData) {
    applyTimeScale();

    const binMinutes = Number.parseInt(binSelect.value, 10);

    tempChart.data.datasets[0].data = parseChartData(allData[0], 't1', binMinutes);

    tempChart.data.datasets[1].data = parseChartData(allData[2], 't2', binMinutes);

    tempChart.data.datasets[2].data = parseChartData(allData[4], 't3', binMinutes);

    humidityChart.data.datasets[0].data = parseChartData(allData[1], 'h1', binMinutes);

    humidityChart.data.datasets[1].data = parseChartData(allData[3], 'h2', binMinutes);

    humidityChart.data.datasets[2].data = parseChartData(allData[5], 'h3', binMinutes);

    tempChart.update();
    humidityChart.update();
}
/******************************************************************************
 * CURRENT VALUE CARDS
 ******************************************************************************/

function getLatestValidRecord(feedPoints) {
    if (!Array.isArray(feedPoints)) {
        return null;
    }

    for (const item of feedPoints) {
        const record = parseSensorPayload(item.value);

        if (record) {
            return record;
        }
    }

    return null;
}

function updateCurrentCards(allData) {
    SENSOR_KEYS.forEach((sensorKey, index) => {
        const record = getLatestValidRecord(allData[index]);

        if (!record) {
            return;
        }

        const displayReading = getDisplayReading(sensorKey, record.reading);

        const valueElement = document.getElementById(`val-${sensorKey}`);

        if (valueElement) {
            valueElement.innerText = displayReading.toFixed(1);
        }

        const nodeId = sensorKey.slice(1);

        const timeElement = document.getElementById(`time-${nodeId}`);

        if (timeElement) {
            timeElement.innerText = record.timestamp.toLocaleTimeString([], {
                hour: '2-digit',

                minute: '2-digit',
            });
        }
    });
}
/******************************************************************************
 * TIME SCALE MANAGEMENT
 ******************************************************************************/

function applyTimeScale() {
    const hours = Number.parseInt(rangeSelect.value, 10);

    const now = Date.now();

    const minTime = now - hours * 60 * 60 * 1000;

    let unit = 'hour';

    let stepSize = 1;

    if (hours <= 4) {
        unit = 'minute';
        stepSize = 30;
    } else if (hours <= 24) {
        unit = 'hour';
        stepSize = 3;
    } else if (hours <= 168) {
        unit = 'day';
        stepSize = 1;
    } else if (hours <= 720) {
        unit = 'week';
        stepSize = 1;
    } else {
        unit = 'month';
        stepSize = 1;
    }

    [tempChart, humidityChart].forEach((chart) => {
        chart.options.scales.x.min = minTime;

        chart.options.scales.x.max = now;

        chart.options.scales.x.time.unit = unit;

        chart.options.scales.x.time.stepSize = stepSize;
    });
}

/******************************************************************************
 * LIVE MQTT UPDATES
 ******************************************************************************/

function connectLiveMqtt() {
    /*
     * Avoid creating another MQTT client
     * each time the historical range changes.
     */
    if (client) {
        return;
    }

    statusEl.innerText = 'Connecting live...';

    statusEl.className =
        'px-3 py-1 rounded-full ' + 'text-xs font-semibold ' + 'bg-amber-500 text-slate-950';

    const brokerUrl = 'wss://io.adafruit.com/mqtt';

    const options = {
        username: config.username,

        password: config.apiKey,

        clientId: 'tl_web_' + Math.random().toString(16).slice(2, 10),
    };

    client = mqtt.connect(brokerUrl, options);

    const topicMap = {};

    const topics = SENSOR_KEYS.map((sensorKey) => {
        const topic = getMqttTopic(sensorKey);

        if (!topic) {
            return null;
        }

        topicMap[topic] = sensorKey;

        return topic;
    }).filter((topic) => topic !== null);

    client.on('connect', () => {
        statusEl.innerText = 'Live Connected';

        statusEl.className =
            'px-3 py-1 rounded-full ' +
            'text-xs font-semibold ' +
            'bg-emerald-500 ' +
            'text-slate-950';

        client.subscribe(topics, (error) => {
            if (error) {
                console.error('MQTT subscribe error:', error);
            }
        });
    });

    client.on('close', () => {
        statusEl.innerText = 'Live Offline';

        statusEl.className =
            'px-3 py-1 rounded-full ' +
            'text-xs font-semibold ' +
            'bg-rose-500 ' +
            'text-slate-100';
    });

    client.on('error', (error) => {
        console.error('MQTT client error:', error);
    });

    client.on('message', (topic, message) => {
        const sensorKey = topicMap[topic];

        if (!sensorKey) {
            return;
        }

        const payloadText = message.toString();

        const record = parseSensorPayload(payloadText);

        if (!record) {
            return;
        }

        /*
         * Add the live message to the same
         * arrays used by the historical data.
         *
         * This keeps chart binning and
         * calibration consistent.
         */
        if (latestAllData) {
            const dataIndex = SENSOR_KEYS.indexOf(sensorKey);

            if (dataIndex >= 0) {
                latestAllData[dataIndex].unshift({
                    value: payloadText,
                });

                /*
                 * Prevent unbounded browser
                 * memory growth during long use.
                 */
                if (latestAllData[dataIndex].length > 10000) {
                    latestAllData[dataIndex].length = 10000;
                }
            }

            updateChartsFromData(latestAllData);

            updateCurrentCards(latestAllData);
        }
    });
}

/******************************************************************************
 * DIAGNOSTICS TABLES
 ******************************************************************************/

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function prettyColumnName(name) {
    return name
        .replaceAll('_', ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/\b\w/g, (c) => c.toUpperCase());
}

function makeDiagnosticsRows(feedData, node) {
    const rows = [];

    feedData.forEach((item) => {
        const payload = parseDiagnosticsPayload(item);

        if (!payload) {
            return;
        }

        const timestamp = getPayloadTimestamp(payload, item);

        if (!timestamp) {
            return;
        }

        const row = {
            Timestamp: timestamp,
            Node: node.suffix,
        };

        Object.entries(payload).forEach(([key, value]) => {
            if (key !== 'Timestamp' && key !== 'timestamp') {
                row[key] = value;
            }
        });

        rows.push(row);
    });

    return rows;
}

async function loadDiagnosticsRows() {
    const hours = Number.parseInt(rangeSelect.value, 10);

    const requests = NODES.map(async (node) => {
        const apiPath = getDiagnosticsApiPath(node);

        if (!apiPath) {
            return [];
        }

        const data = await fetchFeedData(apiPath, hours, 1000);

        return makeDiagnosticsRows(data, node);
    });

    const nodeRows = await Promise.all(requests);

    return nodeRows.flat();
}

function renderDiagnosticsTable(container, rows) {
    if (!rows.length) {
        container.innerHTML = '<div class="text-sm text-slate-400">No data available.</div>';

        return;
    }

    const fieldNames = new Set();

    rows.forEach((row) => {
        Object.keys(row).forEach((key) => {
            if (key !== 'Timestamp' && key !== 'Node') {
                fieldNames.add(key);
            }
        });
    });

    const columns = ['Timestamp', 'Node', ...Array.from(fieldNames).sort()];

    rows.sort((a, b) => b.Timestamp.getTime() - a.Timestamp.getTime());

    const headerHtml = columns
        .map(
            (column) => `
                <th
                    class="px-3 py-2 border-b border-slate-600
                           text-left whitespace-nowrap">
                    ${escapeHtml(prettyColumnName(column))}
                </th>
            `
        )
        .join('');

    const bodyHtml = rows
        .map(
            (row) => `
                <tr class="border-b border-slate-700">
                    ${columns
                        .map(
                            (column) => `
                                <td class="px-3 py-2 whitespace-nowrap">
                                    ${formatDiagnosticsValue(column, row[column])}
                                </td>
                            `
                        )
                        .join('')}
                </tr>
            `
        )
        .join('');

    container.innerHTML = `
        <table class="min-w-full text-xs">
            <thead class="text-slate-300">
                <tr>${headerHtml}</tr>
            </thead>
            <tbody class="text-slate-200">
                ${bodyHtml}
            </tbody>
        </table>
    `;
}

function formatDiagnosticsValue(column, value) {
    if (value === undefined || value === null) {
        return '';
    }

    if (column === 'Timestamp' && value instanceof Date) {
        return escapeHtml(value.toLocaleString());
    }

    if (typeof value === 'object') {
        return escapeHtml(JSON.stringify(value));
    }

    return escapeHtml(String(value));
}

async function showStatusTable() {
    statusTableContainer.innerHTML = '<div class="text-sm text-slate-400">Loading...</div>';

    try {
        const allRows = await loadDiagnosticsRows();
        const statusRows = allRows.filter((row) => String(row.type).toLowerCase() === 'status');

        renderDiagnosticsTable(statusTableContainer, statusRows);
    } catch (error) {
        console.error('Status table error:', error);

        statusTableContainer.innerHTML =
            '<div class="text-sm text-rose-400">Unable to load status data.</div>';
    }
}

async function showLogTable() {
    logTableContainer.innerHTML = '<div class="text-sm text-slate-400">Loading...</div>';

    try {
        const allRows = await loadDiagnosticsRows();

        const logRows = allRows.filter((row) => String(row.Type).toLowerCase() !== 'status');

        renderDiagnosticsTable(logTableContainer, logRows);
    } catch (error) {
        console.error('Log table error:', error);

        logTableContainer.innerHTML =
            '<div class="text-sm text-rose-400">Unable to load log data.</div>';
    }
}

/******************************************************************************
 * CSV EXPORT
 ******************************************************************************/

function downloadCurrentChartData() {
    const table = new Map();

    function addDataset(chart, columnName, datasetIndex) {
        chart.data.datasets[datasetIndex].data.forEach((point) => {
            const timestampMs = point.x.getTime();

            if (!table.has(timestampMs)) {
                table.set(timestampMs, {
                    Timestamp: formatTimestamp(point.x),

                    Temp1: '',
                    Temp2: '',
                    Temp3: '',

                    Humidity1: '',
                    Humidity2: '',
                    Humidity3: '',
                });
            }

            table.get(timestampMs)[columnName] = point.y;
        });
    }

    addDataset(tempChart, 'Temp1', 0);

    addDataset(tempChart, 'Temp2', 1);

    addDataset(tempChart, 'Temp3', 2);

    addDataset(humidityChart, 'Humidity1', 0);

    addDataset(humidityChart, 'Humidity2', 1);

    addDataset(humidityChart, 'Humidity3', 2);

    const rows = [
        [
            'Timestamp',

            `Temp1_` + DISPLAY_TEMPERATURE_UNIT,

            `Temp2_` + DISPLAY_TEMPERATURE_UNIT,

            `Temp3_` + DISPLAY_TEMPERATURE_UNIT,

            'Humidity1',
            'Humidity2',
            'Humidity3',
        ],
    ];

    Array.from(table.keys())
        .sort((a, b) => a - b)
        .forEach((timestampMs) => {
            const row = table.get(timestampMs);

            rows.push([
                row.Timestamp,
                row.Temp1,
                row.Temp2,
                row.Temp3,
                row.Humidity1,
                row.Humidity2,
                row.Humidity3,
            ]);
        });

    const csv = rows.map((row) => row.map(csvEscape).join(',')).join('\n');

    const blob = new Blob([csv], {
        type: 'text/csv',
    });

    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');

    link.href = url;

    link.download = `tres-lunas-` + `${new Date().toISOString().slice(0, 10)}.csv`;

    link.click();

    URL.revokeObjectURL(url);
}

function csvEscape(value) {
    const text = String(value);

    if (text.includes(',') || text.includes('"') || text.includes('\n')) {
        return `"${text.replaceAll('"', '""')}"`;
    }

    return text;
}

function formatTimestamp(date) {
    const pad = (number) => String(number).padStart(2, '0');

    return (
        `${date.getFullYear()}-` +
        `${pad(date.getMonth() + 1)}-` +
        `${pad(date.getDate())} ` +
        `${pad(date.getHours())}:` +
        `${pad(date.getMinutes())}:` +
        `${pad(date.getSeconds())}`
    );
}

/******************************************************************************
 * EVENT HANDLERS
 ******************************************************************************/

showStatusTableBtn.addEventListener('click', async () => {
    statusTableContainer.classList.toggle('hidden');

    if (!statusTableContainer.classList.contains('hidden')) {
        await showStatusTable();
    }
});

showLogTableBtn.addEventListener('click', async () => {
    logTableContainer.classList.toggle('hidden');

    if (!logTableContainer.classList.contains('hidden')) {
        await showLogTable();
    }
});

saveBtn.addEventListener('click', () => {
    config = {
        username: document.getElementById('input-username').value.trim(),

        apiKey: document.getElementById('input-key').value.trim(),
    };

    if (!config.username || !config.apiKey) {
        alert('Missing settings.');
        return;
    }

    localStorage.setItem('mqtt_dht11_config', JSON.stringify(config));

    modalEl.classList.add('hidden');

    disconnectBtn.classList.remove('hidden');

    buildCharts();
    updateTemperatureUnitLabels();
    loadHistoricalData();
});

disconnectBtn.addEventListener('click', () => {
    if (!confirm('Clear settings?')) {
        return;
    }

    localStorage.removeItem('mqtt_dht11_config');

    if (client) {
        client.end(true);
        client = null;
    }

    if (tempChart) {
        tempChart.destroy();
        tempChart = null;
    }

    if (humidityChart) {
        humidityChart.destroy();
        humidityChart = null;
    }

    latestAllData = null;

    SENSOR_KEYS.forEach((sensorKey) => {
        const element = document.getElementById(`val-${sensorKey}`);

        if (element) {
            element.innerText = '--';
        }
    });

    NODES.forEach((node) => {
        const timeElement = document.getElementById(`time-${node.id}`);

        if (timeElement) {
            timeElement.innerText = '--';
        }
    });
});

rangeSelect.addEventListener('change', loadHistoricalData);

binSelect.addEventListener('change', () => {
    if (latestAllData) {
        updateChartsFromData(latestAllData);
    }
});

downloadCsvBtn.addEventListener('click', downloadCurrentChartData);

/******************************************************************************
 * APPLICATION STARTUP
 ******************************************************************************/

init();
