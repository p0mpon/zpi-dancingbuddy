import React, { useEffect, useState } from "react";
import { Navbar, Nav, Form, InputGroup, Button } from "react-bootstrap";
import { Search, Upload } from "react-bootstrap-icons";
import UserMenu from "./UserMenu";
import { Link } from "react-router-dom";
import { ReactComponent as AppLogo } from "../../assets/ob-logo.svg";
import useVideoListParams from "../../hooks/useVideoListParams";

export default function TopBar({ showSearch, onOpenUpload }) {
    const { query, setQuery } = useVideoListParams();
    const [inputValue, setInputValue] = useState(query);

    useEffect(() => {
        setInputValue(query);
    }, [query]);

    useEffect(() => {
        const timer = setTimeout(() => {
            if (inputValue.trim() !== query) {
                setQuery(inputValue);
            }
        }, 350);

        return () => clearTimeout(timer);
    }, [inputValue, query, setQuery]);

    return (
        <Navbar bg="dark" variant="dark" expand="md" sticky="top"
                className="border-bottom border-secondary px-3 px-lg-4 py-2">
            <Link to="/" className="text-decoration-none">
                <Navbar.Brand
                    className="d-flex align-items-center gap-2 fw-bold"
                >
                    <AppLogo style={{width: '40px', height: '40px'}} aria-label="App logo" role="img"/>
                    <span>OnBeat</span>
                </Navbar.Brand>
            </Link>

            <Navbar.Toggle aria-controls="main-navbar" />

            <Navbar.Collapse id="main-navbar">
                {showSearch && (
                    <Form
                        className="d-flex mx-auto gap-3"
                        style={{ width: "420px" }}
                        onSubmit={(e) => {
                            e.preventDefault();
                            setQuery(inputValue);
                        }}
                    >
                        <InputGroup>
                            <Form.Control
                                type="search"
                                placeholder="Search videos"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
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
                        <Upload size={16} />
                        <span>Upload Video</span>
                    </Button>

                    <UserMenu />
                </Nav>
            </Navbar.Collapse>
        </Navbar>
    );
}