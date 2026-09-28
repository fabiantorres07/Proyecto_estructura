import axios from "axios";

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