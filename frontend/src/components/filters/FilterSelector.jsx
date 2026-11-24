import React, { useMemo } from "react";
import { Button, Dropdown, FormCheck } from "react-bootstrap";
import { Filter } from "react-bootstrap-icons";
import useVideoListParams from "../../hooks/useVideoListParams";
import {FILTER_GROUPS} from "../../config/filters";

function normalizeOptions(options = []) {
    return options.map((opt) =>
        typeof opt === "string"
            ? { key: opt.toLowerCase().replace(/\s+/g, "-"), value: opt }
            : opt
    );
}

export default function FilterSelector({filterGroups = FILTER_GROUPS, buttonLabel = null,}) {
    const { getFilters, toggleFilter, clearFilters } = useVideoListParams();

    const normalizedGroups = useMemo(
        () =>
            filterGroups.map((group) => ({
                ...group,
                paramName: group.paramName || "",
                options: normalizeOptions(group.options),
            })),
        [filterGroups]
    );

    const uniqueParamNames = useMemo(
        () => Array.from(new Set(normalizedGroups.map((g) => g.paramName))),
        [normalizedGroups]
    );

    const totalActiveCount = useMemo(() => {
        return normalizedGroups.reduce((sum, group) => {
            const activeInGroup = getFilters(group.paramName);
            const validKeys = new Set(group.options.map((o) => o.key));
            return sum + activeInGroup.filter((k) => validKeys.has(k)).length;
        }, 0);
    }, [normalizedGroups, getFilters]);

    if (normalizedGroups.length === 0) return null;

    return (
        <Dropdown autoClose="outside">
            <Dropdown.Toggle
                variant="outline-secondary"
                id="multi-filter-dropdown"
                className="text-light d-flex align-items-center gap-1"
            >
                <Filter size={14} />
                {buttonLabel && <span>{buttonLabel}</span>}
                {totalActiveCount > 0 && (
                    <span className="badge bg-primary ms-1">{totalActiveCount}</span>
                )}
            </Dropdown.Toggle>

            <Dropdown.Menu
                className="bg-dark border-secondary p-3 shadow"
                style={{ minWidth: `${Math.max(normalizedGroups.length * 190, 220)}px` }}
            >
                <div className="d-flex justify-content-between align-items-center text-light small pb-2 mb-2 border-bottom border-secondary">
                    <span className="fw-semibold">Filters</span>
                    {totalActiveCount > 0 && (
                        <Button
                            variant="link"
                            size="sm"
                            className="p-0 text-decoration-none text-info"
                            onClick={() => clearFilters(uniqueParamNames)}
                        >
                            Clear all
                        </Button>
                    )}
                </div>

                <div className="d-flex flex-row flex-wrap gap-4 align-items-start">
                    {normalizedGroups.map((group) => {
                        const selectedInGroup = new Set(getFilters(group.paramName));
                        const hasGroupSelection = group.options.some((opt) =>
                            selectedInGroup.has(opt.key)
                        );

                        return (
                            <div
                                key={group.id || group.label}
                                className="d-flex flex-column"
                                style={{ minWidth: "160px" }}
                            >
                                <div className="d-flex justify-content-between align-items-center text-secondary small fw-semibold mb-1 px-1">
                                    <span>{group.label}</span>
                                    {hasGroupSelection && (
                                        <button
                                            type="button"
                                            className="btn btn-link btn-sm p-0 text-info text-decoration-none"
                                            style={{ fontSize: "0.75rem" }}
                                            onClick={() => clearFilters(group.paramName)}
                                        >
                                            Reset
                                        </button>
                                    )}
                                </div>

                                <div className="d-flex flex-column gap-1">
                                    {group.options.map((option) => {
                                        const isChecked = selectedInGroup.has(option.key);
                                        const inputId = `${group.paramName}-${option.key}`;

                                        return (
                                            <div
                                                key={option.key}
                                                className="dropdown-item text-light bg-transparent px-2 py-1 rounded"
                                                style={{ cursor: "pointer" }}
                                                onClick={(e) => {
                                                    e.stopPropagation();
                                                    toggleFilter(
                                                        option.key,
                                                        group.paramName
                                                    );
                                                }}
                                            >
                                                <FormCheck
                                                    type="checkbox"
                                                    id={inputId}
                                                    label={option.value}
                                                    checked={isChecked}
                                                    onChange={() => {}}
                                                    className="user-select-none text-light pe-none"
                                                />
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
                </div>
            </Dropdown.Menu>
        </Dropdown>
    );
}