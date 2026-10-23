import React, { useState } from 'react';
import {
  Container, Alert
} from 'react-bootstrap';
import { CheckCircleFill } from 'react-bootstrap-icons';
import SearchBar from './components/PageContent/SearchBar';
import VideoPreview from './components/Modals/VideoPreview';
import VideoUpload from './components/Modals/VideoUpload';
import VideoDisplay from './pages/VideoDisplay';
import VideoList from './pages/VideoList';
import { INITIAL_VIDEOS } from './mock/videos';


export default function App() {
    const [videos, setVideos] = useState(INITIAL_VIDEOS);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentView, setCurrentView] = useState('grid');
  const [activeVideo, setActiveVideo] = useState(null);
  const [previewVideo, setPreviewVideo] = useState(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadSuccessMsg, setUploadSuccessMsg] = useState("");

  const filteredVideos = videos.filter(video => {
                        return video.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          video.author.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const handleAddVideo = (newVideo) => {
    setVideos([newVideo, ...videos]);

    setUploadSuccessMsg("Video uploaded successfully and added to stream feed!");
    setTimeout(() => setUploadSuccessMsg(""), 4000);
  };

  return (
    <div className="bg-dark text-light min-vh-100 pb-5">

      {uploadSuccessMsg && (
        <div className="position-fixed bottom-0 end-0 p-3" style={{ zIndex: 1080 }}>
          <Alert variant="success" onClose={() => setUploadSuccessMsg("")} dismissible className="shadow-lg d-flex align-items-center gap-2">
            <CheckCircleFill size={18} />
            <span>{uploadSuccessMsg}</span>
          </Alert>
        </div>
      )}

      <SearchBar
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        onOpenUpload={() => setIsUploadOpen(true)}
        onGoHome={() => setCurrentView('grid')}
      />

      <Container className="py-4">

        {currentView === 'grid' && (
          <VideoList
          filteredVideos = {filteredVideos}
          resetSearch = {() => { setSearchQuery("") }}
          showPreview = {setPreviewVideo}
          />
        )}
        {currentView === 'watch' && activeVideo && (
          <VideoDisplay
          activeVideo = {activeVideo}
          backToVideoList = {() => setCurrentView('grid')}
          />
        )}

      </Container>

      <VideoPreview
        show = {previewVideo !== null}
        previewVideo = {previewVideo}
        onHide={() => setPreviewVideo(null)}
        switchToVideoView = {() =>{
                  setActiveVideo(previewVideo);
                  setPreviewVideo(null);
                  setCurrentView('watch');
              }
        }
      />

      <VideoUpload
        show={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={handleAddVideo}
      />

    </div>
  );
}