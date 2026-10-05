import { ScenarioLoadSummary } from "../Scenario/ScenarioLoadSummary";

export interface VersionRestoreSummary extends ScenarioLoadSummary {
    restored_version: string;
}