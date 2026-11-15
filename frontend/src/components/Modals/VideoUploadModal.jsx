import React, {useState} from 'react';
import {Modal, Form, Button, Spinner, Alert, Col} from 'react-bootstrap';
import {CheckCircleFill, Upload} from 'react-bootstrap-icons';
import {uploadNewVideo} from "../../api/calls";
import {DIFFICULTY_OPTIONS} from "../../utils/difficulty";

export function VideoUploadModal({ show, onClose }) {
    const [uploadForm, setUploadForm] = useState({
        title: "",
        song_title: "",
        song_author: "",
        description: "",
        difficulty: "",
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
            data.append("song_title", uploadForm.song_title);
            data.append("song_author", uploadForm.song_author);
            data.append("description", uploadForm.description);
            data.append("difficulty", uploadForm.difficulty);
            data.append("file", uploadForm.videoFile);

            console.log(data);

            const response = await uploadNewVideo(data);
            console.log("response", response);

            setUploadSuccessMsg("Video uploaded successfully!");

            setUploadForm({
                title: "",
                song_title: "",
                song_author: "",
                description: "",
                difficulty: "",
                videoFile: null
            });

            onClose();

        } catch (err) {
            setErrorMessage("Failed to upload video. Please check your network.");
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
                    <Modal.Title className="fw-bold fs-4 d-flex align-items-center gap-2">
                        <Upload size={18} className="text-primary"/>
                        <span>Upload New Video</span>
                    </Modal.Title>
                </Modal.Header>

                <Form onSubmit={handleUploadSubmit}>
                    <Modal.Body className="p-4 d-flex flex-column gap-3">
                        <Form.Group>
                            <Form.Label className="fs-6 fw-semibold text-light">Video Title *</Form.Label>
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
                            <Form.Label className="fs-6 fw-semibold text-light">Song Title</Form.Label>
                            <Form.Control
                                type="text"
                                placeholder=""
                                value={uploadForm.song_title}
                                onChange={(e) => setUploadForm({...uploadForm, song_title: e.target.value})}
                                className="bg-dark border-secondary text-light shadow-none"
                            />
                        </Form.Group>

                        <Form.Group>
                            <Form.Label className="fs-6 fw-semibold text-light">Song Artist</Form.Label>
                            <Form.Control
                                type="text"
                                placeholder=""
                                value={uploadForm.song_author}
                                onChange={(e) => setUploadForm({...uploadForm, song_author: e.target.value})}
                                className="bg-dark border-secondary text-light shadow-none"
                            />
                        </Form.Group>

                        <Form.Group>
                            <Form.Label className="fs-6 fw-semibold text-light">Video Description</Form.Label>
                            <Form.Control
                                type="text"
                                placeholder=""
                                value={uploadForm.description}
                                onChange={(e) => setUploadForm({...uploadForm, description: e.target.value})}
                                className="bg-dark border-secondary text-light shadow-none"
                            />
                        </Form.Group>

                        <Form.Group className="mb-3 mb-md-0">
                            <Form.Label className="fs-6 fw-semibold text-light">Video File (.mp4, .mov, .webm)</Form.Label>
                            <Form.Control
                                type="file"
                                required
                                accept="video/*"
                                onChange={(e) => setUploadForm({...uploadForm, videoFile: e.target.files[0]})}
                                className="bg-dark border-secondary text-light shadow-none fs-6"
                            />
                        </Form.Group>

                        <Form.Group className="mb-3 mb-md-0">
                            <Form.Label className="fs-6 fw-semibold text-light">Difficulty</Form.Label>
                            <Form.Select
                                value={uploadForm.difficulty}
                                onChange={(e) => setUploadForm({...uploadForm, difficulty: e.target.value})}
                                aria-label="Difficulty selector"
                                className="bg-dark border-secondary text-light shadow-none"
                            >
                                <option value="">Pick difficulty here</option>
                                {DIFFICULTY_OPTIONS.map(option => (
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
    );
}