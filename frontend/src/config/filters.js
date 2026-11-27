export const DIFFICULTY_OPTIONS = [
    {key: 'beginner', value: 'Beginner'},
    {key: 'intermediate', value: 'Intermediate'},
    {key: 'advanced', value: 'Advanced'},
];

export const ANALYSIS_STATUS_OPTIONS = [
    {key: 'pending', value: 'Pending'},
    {key: 'processing', value: 'Processing'},
    {key: 'done', value: 'Done'},
    {key: 'failed', value: 'Failed'},
]

export const VISIBILITY_OPTIONS = [
    {key: 'public', value: 'Public'},
    {key: 'private', value: 'Private'},
]

export const SORTING_OPTIONS = [
    {key: 'newest', value: "Newest"},
    {key: 'likes', value: "Most Liked"},
    {key: 'played', value: "Most Played"},
];

export const FILTER_GROUPS = [
    {
        id: "difficulty",
        label: "Difficulty",
        paramName: "difficulty",
        options: DIFFICULTY_OPTIONS,
    },
    {
        id: "analysis_status",
        label: "Analysis Status",
        paramName: "analysis_status",
        options: ANALYSIS_STATUS_OPTIONS,
    },
    {
        id: "visibility",
        label: "Visibility",
        paramName: "visibility",
        options: VISIBILITY_OPTIONS,
    }
];

export function getFilterGroupsForMode(modeConfig) {
    const allowedKeys = new Set(modeConfig?.filters || []);
    return FILTER_GROUPS.filter(
        (group) => allowedKeys.has(group.paramName) || allowedKeys.has(group.id)
    );
}