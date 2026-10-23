import React from 'react';
import { Navbar, Nav, Form, InputGroup, Button, Image } from 'react-bootstrap';
import { CollectionPlay, Search, Upload } from 'react-bootstrap-icons';

export default function SearchBar ({searchQuery, setSearchQuery, onOpenUpload, onGoHome}){
    return (
    <Navbar bg="dark" variant="dark" expand="md" sticky="top" className="border-bottom border-secondary px-3 px-lg-4 py-2">
        <Navbar.Brand
          onClick={onGoHome}
          style={{ cursor: 'pointer' }}
          className="d-flex align-items-center gap-2 fw-bold"
        >
          <div className="bg-primary rounded p-2 text-white d-flex align-items-center justify-content-center shadow">
            <CollectionPlay size={20} />
          </div>
          <span>App</span>
        </Navbar.Brand>

        <Navbar.Toggle aria-controls="main-navbar" />

        <Navbar.Collapse id="main-navbar">
          <Form className="d-flex mx-auto" style={{ width: '400px' }} onSubmit={(e) => e.preventDefault()}>
            <InputGroup>
              <Form.Control
                type="search"
                placeholder="Search videos..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="bg-dark text-light border-secondary"
              />
              <Button variant="outline-secondary" className="border-secondary text-light">
                <Search />
              </Button>
            </InputGroup>
          </Form>

          <Nav className="ms-auto align-items-center gap-3">
            <Button
              variant="primary"
              onClick={onOpenUpload}
              className="d-flex align-items-center gap-2 px-3 py-2 fw-semibold shadow-sm"
            >
              <Upload size={16} />
              <span>Upload Video</span>
            </Button>

            <div className="rounded-circle bg-secondary border border-light overflow-hidden d-flex align-items-center justify-content-center" style={{ width: '38px', height: '38px' }}>
              <Image src="https://placehold.co/100x100/3b82f6/ffffff?text=CU" alt="Avatar" fluid />
            </div>
          </Nav>
        </Navbar.Collapse>
      </Navbar>
      );
}