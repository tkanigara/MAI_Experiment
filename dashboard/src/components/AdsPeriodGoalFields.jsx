import { ADS_GOALS, ADS_PLATFORMS, ADS_PLATFORM_SOURCES, PLATFORM_LABELS } from "../lib/constants";
import { adsGoalConfiguration, adsPlatformFlags } from "../lib/format";
import { PlatformBadge, StatusBadge } from "./Badges";

export const ADS_PERIOD_TARGET_FIELDS = [
  ["target_monthly", "Monthly KPI target"],
  ["budget_monthly", "Monthly budget (IDR)"],
  ["target_cost_per_result", "Target cost per result (IDR)"],
];

export function initialAdsPeriodGoals(client, period = null) {
  const connected = new Set(adsPlatformFlags(client));
  return Object.fromEntries(ADS_PLATFORMS.map((platform) => {
    const configured = connected.has(platform) ? adsGoalConfiguration(period, platform) : [];
    const byKey = Object.fromEntries(configured.map((goal) => [goal.key, goal]));
    return [platform, Object.fromEntries((ADS_GOALS[platform] || []).map((goal) => [
      goal.key,
      { ...byKey[goal.key], key: goal.key, enabled: Boolean(byKey[goal.key]) },
    ]))];
  }));
}

export function serializeAdsPeriodGoals(goals, client) {
  return Object.fromEntries(adsPlatformFlags(client).map((platform) => [
    platform,
    Object.values(goals[platform] || {})
      .filter((goal) => goal.enabled)
      .map(({ enabled, ...goal }) => Object.fromEntries(
        Object.entries(goal).map(([key, value]) => [key, value === "" ? null : value]),
      )),
  ]));
}

export default function AdsPeriodGoalFields({ client, goals, onChange }) {
  const connected = new Set(adsPlatformFlags(client));

  function updateGoal(platform, goalKey, field, value) {
    onChange((current) => ({
      ...current,
      [platform]: {
        ...current[platform],
        [goalKey]: { ...current[platform][goalKey], [field]: value },
      },
    }));
  }

  return (
    <div>
      <div className="field-label">Goals &amp; KPI for this report month</div>
      <div className="field-note">Select only the goals active in this month. KPI, budget, and cost targets can change independently next month.</div>
      <div className="ads-platform-picker">
        {ADS_PLATFORMS.filter((platform) => connected.has(platform)).map((platform) => {
          const source = ADS_PLATFORM_SOURCES[platform];
          return (
            <div className="ads-platform-config is-selected" key={platform}>
              <div className="ads-platform-option">
                <PlatformBadge platform={platform} />
                <span><strong>{PLATFORM_LABELS[platform]} Ads</strong><small>{source.label}</small></span>
                <StatusBadge text={source.available ? "Available" : "Coming soon"} state={source.available ? "success" : "info"} />
              </div>
              <div className="ads-goal-list">
                {(ADS_GOALS[platform] || []).map((definition) => {
                  const goal = goals[platform]?.[definition.key] || { key: definition.key, enabled: false };
                  return (
                    <div className={`ads-goal-config ${goal.enabled ? "is-selected" : ""}`} key={definition.key}>
                      <label className="ads-goal-toggle">
                        <input type="checkbox" checked={goal.enabled} onChange={(event) => updateGoal(platform, definition.key, "enabled", event.target.checked)} />
                        <span><strong>{definition.label}</strong><small>{definition.family.replaceAll("_", " ")}</small></span>
                      </label>
                      {goal.enabled && (
                        <div className="ads-goal-targets">
                          {ADS_PERIOD_TARGET_FIELDS.map(([field, label]) => (
                            <label key={field}>{label}<input type="number" min="0" step="any" value={goal[field] ?? ""} placeholder="Optional" onChange={(event) => updateGoal(platform, definition.key, field, event.target.value)} /></label>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
