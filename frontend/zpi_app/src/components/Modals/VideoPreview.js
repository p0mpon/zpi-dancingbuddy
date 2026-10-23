import React from 'react';
import { Modal, Button } from 'react-bootstrap';
import { PlayFill } from 'react-bootstrap-icons';

export default function VideoPreview ({show, previewVideo, onHide, switchToVideoView}){
return (
<Modal
        show={show}
        onHide={onHide}
        centered
        size="lg"
        contentClassName="bg-black text-light border border-secondary rounded-4 shadow-lg"
      >
        {previewVideo && (
          <>
            <Modal.Body className="p-0">
              <div className="ratio ratio-16x9 bg-dark">
                <video
                  src={previewVideo.videoUrl}
                  controls
                  autoPlay
                  muted
                  poster={previewVideo.thumbnail}
                  className="w-100 h-100 object-fit-contain"
                />
              </div>

              <div className="p-4">
                <h4 className="fw-bold text-light mb-1">{previewVideo.title}</h4>
                <p className="text-muted fs-7 mb-3">
                  By <strong className="text-light">{previewVideo.author}</strong>
                </p>
              </div>
            </Modal.Body>

            <Modal.Footer className="border-top border-secondary">
              <Button variant="outline-secondary" size="sm" onClick={onHide}>
                Close
              </Button>
              <Button
                variant="primary"
                size="sm"
                className="d-flex align-items-center gap-2"
                onClick={switchToVideoView}
              >
                <PlayFill size={15} />
                <span>Watch Full Video</span>
              </Button>
            </Modal.Footer>
          </>
        )}
      </Modal>)}