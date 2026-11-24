import DetailsTab from "../components/Modals/PreviewModals/Tabs/DetailsTab";
import DanceAttemptsTab from "../components/Modals/PreviewModals/Tabs/DanceAttemptsTab";
import EditorTab from "../components/Modals/PreviewModals/Tabs/EditorTab";

export const PREVIEW_MODALS_CONFIGS = {
    general: [
        { eventKey: "details", title: "Details", Component: DetailsTab },
        { eventKey: "attempts", title: "Dance Attempts", Component: DanceAttemptsTab },
    ],
    user_specific: [
        { eventKey: "details", title: "Details", Component: DetailsTab },
        { eventKey: "attempts", title: "Dance Attempts", Component: DanceAttemptsTab },
        { eventKey: "editor", title: "Editor", Component: EditorTab },
    ]
};