import http from "k6/http";
import { check, group, sleep } from "k6";
import { Rate } from "k6/metrics";

const BASE_URL = (__ENV.BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const TEST_TYPE = (__ENV.TEST_TYPE || "smoke").toLowerCase();
const THINK_TIME_MIN = numberEnv("THINK_TIME_MIN", 0.5);
const THINK_TIME_MAX = numberEnv("THINK_TIME_MAX", 1.5);

const responseValidationFailures = new Rate("response_validation_failed");

const scenarioProfiles = {
  smoke: {
    executor: "constant-vus",
    vus: 1,
    duration: "30s",
  },
  load: {
    executor: "ramping-vus",
    startVUs: 1,
    stages: [
      { duration: "1m", target: 5 },
      { duration: "3m", target: 20 },
      { duration: "1m", target: 0 },
    ],
  },
  stress: {
    executor: "ramping-vus",
    startVUs: 1,
    stages: [
      { duration: "1m", target: 10 },
      { duration: "2m", target: 25 },
      { duration: "2m", target: 50 },
      { duration: "2m", target: 100 },
      { duration: "1m", target: 0 },
    ],
  },
  spike: {
    executor: "ramping-vus",
    startVUs: 1,
    stages: [
      { duration: "20s", target: 5 },
      { duration: "10s", target: 100 },
      { duration: "1m", target: 100 },
      { duration: "30s", target: 0 },
    ],
  },
  soak: {
    executor: "ramping-vus",
    startVUs: 1,
    stages: [
      { duration: "2m", target: 10 },
      { duration: "30m", target: 10 },
      { duration: "2m", target: 0 },
    ],
  },
};

if (!scenarioProfiles[TEST_TYPE]) {
  throw new Error(
    `Unknown TEST_TYPE '${TEST_TYPE}'. Use smoke, load, stress, spike, or soak.`,
  );
}

export const options = {
  scenarios: {
    dashboard_api: {
      ...scenarioProfiles[TEST_TYPE],
      gracefulStop: "30s",
      tags: { test_type: TEST_TYPE },
    },
  },
  thresholds: {
    checks: ["rate>0.99"],
    http_req_failed: ["rate<0.01"],
    response_validation_failed: ["rate<0.01"],
    "http_req_duration{endpoint:clients}": ["p(95)<500"],
    "http_req_duration{endpoint:platforms}": ["p(95)<750"],
    "http_req_duration{endpoint:overview}": ["p(95)<1500"],
  },
  noConnectionReuse: false,
  userAgent: "mai-dashboard-k6-load-test/1.0",
};

export function setup() {
  const clientsResponse = http.get(`${BASE_URL}/api/clients`, requestParams("clients"));
  const clients = parseJson(clientsResponse, "client list");

  if (clientsResponse.status !== 200 || !Array.isArray(clients) || clients.length === 0) {
    throw new Error(
      `Cannot start load test: GET /api/clients returned status ${clientsResponse.status} or no clients.`,
    );
  }

  const selectedClient = selectClient(clients);
  const clientId = String(selectedClient.id);
  const platformsResponse = http.get(
    `${BASE_URL}/api/clients/${encodeURIComponent(clientId)}/platforms`,
    requestParams("platforms"),
  );
  const platformPayload = parseJson(platformsResponse, "platform metadata");

  if (platformsResponse.status !== 200 || !platformPayload) {
    throw new Error(
      `Cannot start load test: platform metadata returned status ${platformsResponse.status}.`,
    );
  }

  const reportMonth = selectReportMonth(platformPayload.report_months || []);
  const platforms = selectPlatforms(selectedClient, platformPayload.profiles || []);

  if (platforms.length === 0) {
    throw new Error(
      `Cannot start load test: client '${selectedClient.client_code}' has no connected platforms.`,
    );
  }

  console.log(
    `[k6] type=${TEST_TYPE} client=${selectedClient.client_code} ` +
      `period=${reportMonth ? reportMonth.label : "latest/default"} ` +
      `platforms=${platforms.join(",")}`,
  );

  return {
    clientId,
    clientCode: selectedClient.client_code,
    periodId: reportMonth ? String(reportMonth.id) : "",
    platforms,
  };
}

export default function (context) {
  group("dashboard read flow", () => {
    const clientsResponse = http.get(`${BASE_URL}/api/clients`, requestParams("clients"));
    validateResponse(clientsResponse, "clients", (body) => Array.isArray(body));

    const platformsResponse = http.get(
      `${BASE_URL}/api/clients/${encodeURIComponent(context.clientId)}/platforms`,
      requestParams("platforms"),
    );
    validateResponse(
      platformsResponse,
      "platforms",
      (body) => body && body.client && Array.isArray(body.report_months),
    );

    const platform = context.platforms[Math.floor(Math.random() * context.platforms.length)];
    const periodQuery = context.periodId
      ? `?period_id=${encodeURIComponent(context.periodId)}`
      : "";
    const overviewResponse = http.get(
      `${BASE_URL}/api/clients/${encodeURIComponent(context.clientId)}` +
        `/platforms/${encodeURIComponent(platform)}/overview${periodQuery}`,
      requestParams("overview", { platform }),
    );
    validateResponse(
      overviewResponse,
      "overview",
      (body) => body && typeof body === "object" && !Array.isArray(body),
    );
  });

  sleep(randomBetween(THINK_TIME_MIN, THINK_TIME_MAX));
}

function requestParams(endpoint, extraTags = {}) {
  const headers = { Accept: "application/json" };
  if (__ENV.AUTH_TOKEN) {
    headers.Authorization = `Bearer ${__ENV.AUTH_TOKEN}`;
  }
  return {
    headers,
    tags: { endpoint, ...extraTags },
    timeout: __ENV.REQUEST_TIMEOUT || "15s",
  };
}

function validateResponse(response, label, bodyValidator) {
  const body = parseJson(response, label);
  const valid = check(response, {
    [`${label}: status is 200`]: (res) => res.status === 200,
    [`${label}: response is valid`]: () => body !== null && bodyValidator(body),
  });
  responseValidationFailures.add(!valid, { endpoint: label });
}

function parseJson(response, label) {
  try {
    return response.json();
  } catch (_error) {
    console.error(
      `[k6] ${label} returned non-JSON response: status=${response.status}`,
    );
    return null;
  }
}

function selectClient(clients) {
  if (__ENV.CLIENT_ID) {
    const match = clients.find((client) => String(client.id) === String(__ENV.CLIENT_ID));
    if (!match) {
      throw new Error(`CLIENT_ID '${__ENV.CLIENT_ID}' was not found.`);
    }
    return match;
  }
  if (__ENV.CLIENT_CODE) {
    const expectedCode = String(__ENV.CLIENT_CODE).toLowerCase();
    const match = clients.find(
      (client) => String(client.client_code).toLowerCase() === expectedCode,
    );
    if (!match) {
      throw new Error(`CLIENT_CODE '${__ENV.CLIENT_CODE}' was not found.`);
    }
    return match;
  }
  return clients.find((client) => connectedPlatforms(client).length > 0) || clients[0];
}

function selectReportMonth(reportMonths) {
  if (__ENV.PERIOD_ID) {
    const match = reportMonths.find(
      (month) => String(month.id) === String(__ENV.PERIOD_ID),
    );
    if (!match) {
      throw new Error(`PERIOD_ID '${__ENV.PERIOD_ID}' was not found for the client.`);
    }
    return match;
  }
  if (__ENV.MONTH_SLUG) {
    const match = reportMonths.find(
      (month) => String(month.slug).toLowerCase() === String(__ENV.MONTH_SLUG).toLowerCase(),
    );
    if (!match) {
      throw new Error(`MONTH_SLUG '${__ENV.MONTH_SLUG}' was not found for the client.`);
    }
    return match;
  }
  return reportMonths.length > 0 ? reportMonths[0] : null;
}

function selectPlatforms(client, profiles) {
  if (__ENV.PLATFORM) {
    return String(__ENV.PLATFORM)
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean);
  }

  const result = connectedPlatforms(client);
  for (const profile of profiles) {
    const platform = String(profile.platform || "").toLowerCase();
    if (platform && !result.includes(platform)) {
      result.push(platform);
    }
  }
  return result;
}

function connectedPlatforms(client) {
  const flags = {
    instagram: client.has_instagram,
    facebook: client.has_facebook,
    tiktok: client.has_tiktok,
    youtube: client.has_youtube,
    linkedin: client.has_linkedin,
    threads: client.has_threads,
  };
  return Object.entries(flags)
    .filter(([, enabled]) => Boolean(enabled))
    .map(([platform]) => platform);
}

function randomBetween(minimum, maximum) {
  return minimum + Math.random() * Math.max(0, maximum - minimum);
}

function numberEnv(name, fallback) {
  const parsed = Number(__ENV[name]);
  return Number.isFinite(parsed) ? parsed : fallback;
}
