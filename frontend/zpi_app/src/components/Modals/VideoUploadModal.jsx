import React, {useState} from 'react';
import {Modal, Form, Button, Spinner, Alert, Col} from 'react-bootstrap';
import {CheckCircleFill, Upload} from 'react-bootstrap-icons';
import {postVideo} from "../../api/calls";

export function VideoUploadModal({show, onClose, onUploadSuccess}) {
    const [uploadForm, setUploadForm] = useState({
        title: "",
        description: "",
        category: "Development",
        videoFile: null,
    });
    const [isUploading, setIsUploading] = useState(false);
    const [errorMessage, setErrorMessage] = useState("");
    const [uploadSuccessMsg, setUploadSuccessMsg] = useState("");

    async function handleUploadSubmit(e) {
        e.preventDefault();

        if (!uploadForm.videoFile) {
            setErrorMessage("Please select a video file to upload.");
            return;
        }

        setIsUploading(true);
        setErrorMessage("");

        try {
            const data = new FormData();
            data.append("title", uploadForm.title);
            data.append("description", uploadForm.description);
            data.append("author", uploadForm.author);
            data.append("video", uploadForm.videoFile);
            
            console.log(data);

            const video = await postVideo(data).then((res) => {
                console.log()
            });

            setUploadSuccessMsg("Video uploaded successfully!");

            setUploadForm({title: "", description: "", category: "Development", videoFile: null});

            if (onUploadSuccess) onUploadSuccess(video);
            onClose();

        } catch (err) {
            console.error("Upload error:", err);
            setErrorMessage(err.response?.data?.message || "Failed to upload video. Please check your network.");
        } finally {
            setIsUploading(false);
        }
    }

    return (
        <>
            {uploadSuccessMsg && (
                <div className="position-fixed bottom-0 end-0 p-3" style={{zIndex: 1080}}>
                    <Alert variant="success" onClose={() => setUploadSuccessMsg("")} dismissible
                           className="shadow-lg d-flex align-items-center gap-2">
                        <CheckCircleFill size={18}/>
                        <span>{uploadSuccessMsg}</span>
                    </Alert>
                </div>
            )}

            <Modal
                show={show}
                onHide={onClose}
                centered
                contentClassName="bg-black text-light border border-secondary rounded-4 shadow-lg"
            >
                <Modal.Header closeButton closeVariant="white" className="border-bottom border-secondary">
                    <Modal.Title className="fw-bold fs-5 d-flex align-items-center gap-2">
                        <Upload size={18} className="text-primary"/>
                        <span>Upload New Video</span>
                    </Modal.Title>
                </Modal.Header>

                <Form onSubmit={handleUploadSubmit}>
                    <Modal.Body className="p-4 d-flex flex-column gap-3">
                        <Form.Group>
                            <Form.Label className="fs-7 fw-semibold text-light">Video Title *</Form.Label>
                            <Form.Control
                                type="text"
                                required
                                placeholder=""
                                value={uploadForm.title}
                                onChange={(e) => setUploadForm({...uploadForm, title: e.target.value})}
                                className="bg-dark border-secondary text-light shadow-none"
                            />
                        </Form.Group>

                        <Form.Group>
                            <Form.Label className="fs-7 fw-semibold text-light">Video Description</Form.Label>
                            <Form.Control
                                type="text"
                                placeholder=""
                                value={uploadForm.description}
                                onChange={(e) => setUploadForm({...uploadForm, description: e.target.value})}
                                className="bg-dark border-secondary text-light shadow-none"
                            />
                        </Form.Group>

                        <Form.Group className="mb-3 mb-md-0">
                            <Form.Label className="fs-7 fw-semibold text-light">Video File (.mp4)</Form.Label>
                            <Form.Control
                                type="file"
                                accept="video/*"
                                onChange={(e) => setUploadForm({...uploadForm, videoFile: e.target.files[0]})}
                                className="bg-dark border-secondary text-light shadow-none fs-8"
                            />
                        </Form.Group>
                        {errorMessage && (
                            <Alert variant="danger" className="py-2 px-3 m-0 fs-8">
                                {errorMessage}
                            </Alert>
                        )}
                    </Modal.Body>

                    <Modal.Footer className="border-top border-secondary">
                        <Col xs="auto">
                            <Button variant="outline-secondary" size="sm" onClick={onClose} disabled={isUploading}>
                                Cancel
                            </Button>
                        </Col>
                        <Col xs="auto">
                            <Button variant="primary" size="sm" type="submit" disabled={isUploading}>
                                {isUploading ? (
                                    <>
                                        <Spinner animation="border" size="sm" className="me-2"/>
                                        <span>Uploading...</span>
                                    </>
                                ) : (
                                    <span>Publish Video</span>
                                )}
                            </Button>
                        </Col>
                    </Modal.Footer>
                </Form>
            </Modal>
        </>
    )
}