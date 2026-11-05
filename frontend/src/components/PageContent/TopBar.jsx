import React from 'react';
import {Navbar, Nav, Form, InputGroup, Button} from 'react-bootstrap';
import {CollectionPlay, Search, Upload} from 'react-bootstrap-icons';
import UserMenu from "./UserMenu";
import {useSearchParams, Link} from "react-router-dom";

export default function TopBar({showSearch, onOpenUpload}) {
    const [searchParams, setSearchParams] = useSearchParams();
    const searchQuery = searchParams.get('search') || '';

    const handleSearch = (e) => {
        const value = e.target.value;
        if (value) {
            setSearchParams({search: value});
        } else {
            setSearchParams({});
        }
    };
    return (
        <Navbar bg="dark" variant="dark" expand="md" sticky="top"
                className="border-bottom border-secondary px-3 px-lg-4 py-2">
            <Link to="/">
                <Navbar.Brand
                    className="d-flex align-items-center gap-2 fw-bold"
                >
                    <div
                        className="bg-primary rounded p-2 text-white d-flex align-items-center justify-content-center shadow">
                        <CollectionPlay size={20}/>
                    </div>
                    <span>App</span>
                </Navbar.Brand>
            </Link>

            <Navbar.Toggle aria-controls="main-navbar"/>

            <Navbar.Collapse id="main-navbar">
                {showSearch && (
                    <Form className="d-flex mx-auto" style={{width: '400px'}} onSubmit={(e) => e.preventDefault()}>
                        <InputGroup>
                            <Form.Control
                                type="search"
                                placeholder="Search videos"
                                value={searchQuery}
                                onChange={handleSearch}
                                className="bg-dark text-light border-secondary"
                            />
                            <Button variant="outline-secondary" className="border-secondary text-light">
                                <Search/>
                            </Button>
                        </InputGroup>
                    </Form>
                )}

                <Nav className="ms-auto align-items-center gap-3">
                    <Button
                        variant="primary"
                        onClick={onOpenUpload}
                        className="d-flex align-items-center gap-2 px-3 py-2 fw-semibold shadow-sm"
                    >
                        <Upload size={16}/>
                        <span>Upload Video</span>
                    </Button>

                    <UserMenu/>
                </Nav>
            </Navbar.Collapse>
        </Navbar>
    );
}