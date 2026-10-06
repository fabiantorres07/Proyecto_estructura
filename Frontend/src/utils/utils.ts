import axios from "axios";

export const SCENARIO_STATE_CHANGED_EVENT = "sismolab:scenario-state-changed";
export const SCENARIO_UNDONE_EVENT = SCENARIO_STATE_CHANGED_EVENT;

export const notifyScenarioStateChanged = () => {
    if (typeof window !== "undefined") {
        window.dispatchEvent(new Event(SCENARIO_STATE_CHANGED_EVENT));
    }
};

export const getApiErrorMessage = (error: unknown, fallback: string) => {
    if (axios.isAxiosError(error)) {
        const responseData = error.response?.data;
        const detail = responseData?.detail ?? responseData?.message ?? responseData?.error;

        if (typeof detail === "string") {
            return detail;
        }

        if (Array.isArray(detail)) {
            return detail
                .map((item) => (typeof item?.msg === "string" ? item.msg : null))
                .filter(Boolean)
                .join("; ") || fallback;
        }
    }

    return error instanceof Error ? error.message : fallback;
};

export const formatLocalDateTime = (value: Date | string) => {
    const date = value instanceof Date ? value : new Date(value);
    return new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
        .toISOString()
        .slice(0, 19);
};

export const parseLocalDateTime = (value?: string): Date | null => {
    if (!value || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?$/.test(value)) {
        return null;
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return null;
    }

    const formattedDate = formatLocalDateTime(date);
    const matchesInput = value.length === 16
        ? formattedDate.slice(0, 16) === value && date.getSeconds() === 0
        : formattedDate === value;

    return matchesInput ? date : null;
};