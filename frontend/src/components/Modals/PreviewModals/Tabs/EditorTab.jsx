import {Alert, Button, Form, Modal, Spinner} from "react-bootstrap";
import {useVideo} from "../../../../context/VideoContext";
import {useState} from "react";
import {DIFFICULTY_OPTIONS} from "../../../../config/filters";
import {deleteVideo, editVideo, privateVideo, publishVideo} from "../../../../api/calls";

export default function EditorTab() {
    const {currentVideo, setCurrentVideo, notifyVideoDeleted, onCloseModal, refreshVideo} = useVideo();

    const [draftVideo, setDraftVideo] = useState(() =>
        currentVideo ? structuredClone(currentVideo) : null
    );
    const [isSaving, setIsSaving] = useState(false);
    const [errorMessage, setErrorMessage] = useState(null);
    const [pendingAction, setPendingAction] = useState(null); // null | { type: "visibility" } | { type: "discard" } | { type: "delete" }

    if (!draftVideo) {
        return <div className="text-muted small py-3">No video loaded.</div>;
    }

    const hasUnsavedChanges = Boolean(
        currentVideo &&
        draftVideo &&
        (
            (draftVideo.title ?? "") !== (currentVideo.title ?? "") ||
            (draftVideo.song_title ?? "") !== (currentVideo.song_title ?? "") ||
            (draftVideo.song_author ?? "") !== (currentVideo.song_author ?? "") ||
            (draftVideo.description ?? "") !== (currentVideo.description ?? "") ||
            (draftVideo.difficulty ?? "") !== (currentVideo.difficulty ?? "")
        )
    );

    const isPrivate = draftVideo.visibility === "private";

    const handleVisibilityChange = async () => {
        setIsSaving(true);
        setErrorMessage(null);

        try {
            if (isPrivate) {
                await publishVideo(currentVideo.id);
            } else {
                await privateVideo(currentVideo.id);
            }

            const freshVideo = await refreshVideo(currentVideo.id);
            if (freshVideo) {
                setDraftVideo(structuredClone(freshVideo));
            }
            setPendingAction(null);
        } catch (e) {
            setErrorMessage("Failed to update visibility. Please check if you have set the difficulty option.");
            console.error(e);
            setPendingAction(null);
        } finally {
            setIsSaving(false);
        }
    };

    const handleEditSubmit = async (evt) => {
        evt.preventDefault();
        setIsSaving(true);
        setErrorMessage(null);

        const videoData = {
            title: draftVideo.title?.trim() ?? "",
            song_title: draftVideo.song_title ?? "",
            song_author: draftVideo.song_author ?? "",
            description: draftVideo.description ?? "",
            difficulty: draftVideo.difficulty !== "" ? draftVideo.difficulty : null,
        };

        try {
            await editVideo(currentVideo.id, videoData);

            const freshVideo = await refreshVideo(currentVideo.id);
            if (freshVideo) {
                setDraftVideo(structuredClone(freshVideo));
            }
        } catch (err) {
            setErrorMessage(
                err?.response?.data?.message ||
                err?.response?.data?.detail ||
                err?.message ||
                "Failed to save changes."
            );
            console.error(err);
        } finally {
            setIsSaving(false);
        }
    };

    const handleDiscard = () => {
        if (currentVideo) {
            setDraftVideo(structuredClone(currentVideo));
        }
        setErrorMessage(null);
        setPendingAction(null);
    };

    const handleDeletion = async () => {
        setIsSaving(true);
        setErrorMessage(null);

        try {
            const deletedId = currentVideo.id;
            await deleteVideo(deletedId);

            setPendingAction(null);
            setCurrentVideo(null);
            notifyVideoDeleted?.(deletedId);
            onCloseModal();
        } catch (err) {
            setErrorMessage(
                err?.response?.data?.message ||
                err?.response?.data?.detail ||
                err?.message ||
                "Failed to delete video."
            );
            console.error(err);
            setPendingAction(null);
        } finally {
            setIsSaving(false);
        }
    };
    

    const handleConfirmAction = async () => {
        if (!pendingAction) return;
        if (pendingAction.type === "visibility") {
            await handleVisibilityChange();
        } else if (pendingAction.type === "discard") {
            handleDiscard();
        } else if (pendingAction.type === "delete") {
            await handleDeletion();
        }
    };

    const getModalDetails = () => {
        switch (pendingAction?.type) {
            case "visibility":
                return {
                    title: isPrivate ? "Publish video?" : "Make video private?",
                    body: isPrivate
                        ? "This video will become visible to others."
                        : "This video will be hidden from public view.",
                    confirmText: isPrivate ? "Publish" : "Make Private",
                    variant: "success",
                };
            case "discard":
                return {
                    title: "Discard unsaved changes?",
                    body: "Your current edits will be reverted back to the last saved version.",
                    confirmText: "Discard Changes",
                    variant: "warning",
                };
            case "delete":
                return {
                    title: "Delete video?",
                    body: `Are you sure you want to permanently delete "${draftVideo.title || "this video"}"? This cannot be undone.`,
                    confirmText: "Delete Video",
                    variant: "danger",
                };
            default:
                return {
                    title: "",
                    body: "",
                    confirmText: "Confirm",
                    variant: "primary",
                };
        }
    };

    const modalDetails = getModalDetails();

    return (
        <>
            <div className="d-flex flex-wrap gap-2 mb-2">
                <Button
                    variant="success"
                    size="sm"
                    type="button"
                    onClick={() => setPendingAction({ type: "visibility" })}
                    disabled={isSaving}
                    className="mt-2"
                >
                    {isSaving ? (
                        <>
                            <Spinner animation="border" size="sm" className="me-2" />
                            <span>Saving Changes...</span>
                        </>
                    ) : (
                        <span>{isPrivate ? "Publish" : "Private"}</span>
                    )}
                </Button>

                {hasUnsavedChanges && (
                    <Button
                        variant="outline-secondary"
                        size="sm"
                        type="button"
                        onClick={() => setPendingAction({ type: "discard" })}
                        disabled={isSaving}
                        className="mt-2"
                    >
                        Discard Changes
                    </Button>
                )}
            </div>

            <hr className="border-secondary my-3" />

            <Form
                onSubmit={handleEditSubmit}
                className="overflow-y-auto pe-2"
                style={{ maxHeight: "460px" }}
            >
                <div className="d-flex flex-column gap-3 py-2">
                    <Form.Group>
                        <Form.Label className="fs-6 fw-semibold text-light">
                            Video Title *
                        </Form.Label>
                        <Form.Control
                            type="text"
                            required
                            value={draftVideo.title ?? ""}
                            onChange={(e) =>
                                setDraftVideo((prev) => ({
                                    ...prev,
                                    title: e.target.value,
                                }))
                            }
                            className="bg-dark border-secondary text-light shadow-none"
                        />
                    </Form.Group>

                    <Form.Group>
                        <Form.Label className="fs-6 fw-semibold text-light">
                            Song Title
                        </Form.Label>
                        <Form.Control
                            type="text"
                            value={draftVideo.song_title ?? ""}
                            onChange={(e) =>
                                setDraftVideo((prev) => ({
                                    ...prev,
                                    song_title: e.target.value,
                                }))
                            }
                            className="bg-dark border-secondary text-light shadow-none"
                        />
                    </Form.Group>

                    <Form.Group>
                        <Form.Label className="fs-6 fw-semibold text-light">
                            Song Artist
                        </Form.Label>
                        <Form.Control
                            type="text"
                            value={draftVideo.song_author ?? ""}
                            onChange={(e) =>
                                setDraftVideo((prev) => ({
                                    ...prev,
                                    song_author: e.target.value,
                                }))
                            }
                            className="bg-dark border-secondary text-light shadow-none"
                        />
                    </Form.Group>

                    <Form.Group>
                        <Form.Label className="fs-6 fw-semibold text-light">
                            Video Description
                        </Form.Label>
                        <Form.Control
                            as="textarea"
                            rows={2}
                            value={draftVideo.description ?? ""}
                            onChange={(e) =>
                                setDraftVideo((prev) => ({
                                    ...prev,
                                    description: e.target.value,
                                }))
                            }
                            className="bg-dark border-secondary text-light shadow-none"
                        />
                    </Form.Group>

                    <Form.Group>
                        <Form.Label className="fs-6 fw-semibold text-light">
                            Difficulty
                        </Form.Label>
                        <Form.Select
                            value={draftVideo.difficulty ?? ""}
                            onChange={(e) =>
                                setDraftVideo((prev) => ({
                                    ...prev,
                                    difficulty: e.target.value,
                                }))
                            }
                            className="bg-dark border-secondary text-light shadow-none"
                        >
                            <option value="">Pick difficulty here</option>
                            {DIFFICULTY_OPTIONS.map((option) => (
                                <option key={option.key} value={option.key}>
                                    {option.value}
                                </option>
                            ))}
                        </Form.Select>
                    </Form.Group>

                    {errorMessage && (
                        <Alert variant="danger" className="py-2 px-3 m-0 fs-6">
                            {errorMessage}
                        </Alert>
                    )}

                    <Button
                        variant="success"
                        size="sm"
                        type="submit"
                        disabled={isSaving || !hasUnsavedChanges}
                        className="mt-2"
                    >
                        {isSaving ? (
                            <>
                                <Spinner animation="border" size="sm" className="me-2" />
                                <span>Saving Changes...</span>
                            </>
                        ) : (
                            <span>Save Changes</span>
                        )}
                    </Button>
                </div>
            </Form>

            <hr className="border-secondary my-3" />

            <Button
                variant="outline-danger"
                size="sm"
                type="button"
                disabled={isSaving}
                onClick={() => setPendingAction({ type: "delete" })}
                className="mt-2"
            >
                Delete Video
            </Button>

            <Modal
                show={Boolean(pendingAction)}
                onHide={() => !isSaving && setPendingAction(null)}
                backdrop={isSaving ? "static" : true}
                centered
            >
                <Modal.Header closeButton={!isSaving}>
                    <Modal.Title>{modalDetails.title}</Modal.Title>
                </Modal.Header>
                <Modal.Body>{modalDetails.body}</Modal.Body>
                <Modal.Footer>
                    <Button
                        variant="secondary"
                        type="button"
                        disabled={isSaving}
                        onClick={() => setPendingAction(null)}
                    >
                        Cancel
                    </Button>
                    <Button
                        variant={modalDetails.variant}
                        type="button"
                        disabled={isSaving}
                        onClick={handleConfirmAction}
                    >
                        {isSaving ? (
                            <>
                                <Spinner animation="border" size="sm" className="me-2" />
                                <span>Working...</span>
                            </>
                        ) : (
                            <span>{modalDetails.confirmText}</span>
                        )}
                    </Button>
                </Modal.Footer>
            </Modal>
        </>
    );
}