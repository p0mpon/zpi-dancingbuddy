import React, { useState } from 'react';
import { Modal, Form, Row, Col, Button, Spinner } from 'react-bootstrap';
import { Upload } from 'react-bootstrap-icons';

export default function VideoUpload({show, onClose, onUploadSuccess}){
    const [uploadForm, setUploadForm] = useState({
    title: "",
    description: "",
    category: "Development",
    videoFile: null,
  });
  const [isUploading, setIsUploading] = useState(false);

  const handleUploadSubmit = (e) => {
    e.preventDefault();
    if (!uploadForm.title || !uploadForm.videoFile) return;

    setIsUploading(true);

    setTimeout(() => {
      const newVideoObj = {
        id: Date.now(),
        title: uploadForm.title,
        author: "ya",
        videoUrl: URL.createObjectURL(uploadForm.videoFile),
      };

      onUploadSuccess(newVideoObj);

      setIsUploading(false);
      setUploadForm({ title: "", videoFile: null});
      onClose();
    }, 1200);
  };
    return (
        <Modal
        show={show}
        onHide={onClose}
        centered
        contentClassName="bg-black text-light border border-secondary rounded-4 shadow-lg"
      >
        <Modal.Header closeButton closeVariant="white" className="border-bottom border-secondary">
          <Modal.Title className="fw-bold fs-5 d-flex align-items-center gap-2">
            <Upload size={18} className="text-primary" />
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
                placeholder="e.g., Building a Django REST API with JWT"
                value={uploadForm.title}
                onChange={(e) => setUploadForm({...uploadForm, title: e.target.value})}
                className="bg-dark border-secondary text-light shadow-none"
              />
            </Form.Group>

            <Row>
              <Col md={6}>
                <Form.Group className="mb-3 mb-md-0">
                  <Form.Label className="fs-7 fw-semibold text-light">Video File (.mp4)</Form.Label>
                  <Form.Control
                    type="file"
                    accept="video/*"
                    onChange={(e) => setUploadForm({...uploadForm, videoFile: e.target.files[0]})}
                    className="bg-dark border-secondary text-light shadow-none fs-8"
                  />
                </Form.Group>
              </Col>
            </Row>
          </Modal.Body>

          <Modal.Footer className="border-top border-secondary">
            <Button variant="outline-secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" disabled={isUploading}>
              {isUploading ? (
                <>
                  <Spinner animation="border" size="sm" className="me-2" />
                  <span>Uploading...</span>
                </>
              ) : (
                <span>Publish Video</span>
              )}
            </Button>
          </Modal.Footer>
        </Form>
      </Modal>
      )
      }