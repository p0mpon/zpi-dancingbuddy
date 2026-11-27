
import { useCallback, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import {SORTING_OPTIONS} from "../config/filters";

const DEFAULT_SORT = SORTING_OPTIONS[0].key;
const VALID_SORT_KEYS = new Set(SORTING_OPTIONS.map((option) => option.key));

export default function useVideoListParams() {
    const [searchParams, setSearchParams] = useSearchParams();

    const query = searchParams.get("search") || "";
    const rawSort = searchParams.get("sort");
    const sort = rawSort && VALID_SORT_KEYS.has(rawSort) ? rawSort : DEFAULT_SORT;

    const serializedParams = searchParams.toString();

    const filters = useMemo(
        () => new URLSearchParams(serializedParams).getAll("tag"),
        [serializedParams]
    );

    const getFilters = useCallback(
        (paramName = "tag") => {
            return new URLSearchParams(serializedParams).getAll(paramName);
        },
        [serializedParams]
    );

    const updateParams = useCallback(
        (updater, { replace = true } = {}) => {
            setSearchParams(
                (prev) => {
                    const next = new URLSearchParams(prev);
                    updater(next);
                    return next;
                },
                { replace }
            );
        },
        [setSearchParams]
    );

    const setQuery = useCallback(
        (value) => {
            updateParams((next) => {
                const trimmed = value.trim();
                if (trimmed) next.set("search", trimmed);
                else next.delete("search");
            }, { replace: true });
        },
        [updateParams]
    );

    const toggleFilter = useCallback(
        (value, paramName = "tag") => {
            const normalized = value?.trim();
            if (!normalized || !paramName) return;

            updateParams((next) => {
                const current = next.getAll(paramName);
                next.delete(paramName);
                const updated = current.includes(normalized)
                    ? current.filter((item) => item !== normalized)
                    : [...current, normalized];

                updated.forEach((item) => next.append(paramName, item));
            }, { replace: false });
        },
        [updateParams]
    );

    const setSort = useCallback(
        (newSort) => {
            const nextSort = VALID_SORT_KEYS.has(newSort) ? newSort : DEFAULT_SORT;
            updateParams((next) => {
                if (nextSort === DEFAULT_SORT) next.delete("sort");
                else next.set("sort", nextSort);
            }, { replace: false });
        },
        [updateParams]
    );

    const clearFilters = useCallback(
        (paramNames) => {
            if (!paramNames) return;
            const targets = Array.isArray(paramNames) ? paramNames : [paramNames];

            updateParams((next) => {
                targets.forEach((name) => {
                    if (name) next.delete(name);
                });
            }, { replace: false });
        },
        [updateParams]
    );

    return {
        query,
        filters,
        getFilters,
        sort,
        setQuery,
        toggleFilter,
        setSort,
        clearFilters,
    };
}