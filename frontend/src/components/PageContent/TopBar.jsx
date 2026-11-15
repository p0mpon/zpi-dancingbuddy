import React, {useEffect, useState} from 'react';
import {Navbar, Nav, Form, InputGroup, Button, Dropdown, FormCheck} from 'react-bootstrap';
import {CollectionPlay, Filter, Search, Upload} from 'react-bootstrap-icons';
import UserMenu from "./UserMenu";
import {useSearchParams, Link} from "react-router-dom";
import {DIFFICULTY_OPTIONS} from "../../utils/difficulty";
import {seedVideos} from "../../utils/video_seed";

export default function TopBar({showSearch, onOpenUpload}) {
    const [searchParams, setSearchParams] = useSearchParams();
    const searchQuery = searchParams.get('search') || '';

    const difficulties = searchParams.get('difficulty');
    const selectedDifficulties = difficulties ? difficulties.split(',') : [];

    const [inputValue, setInputValue] = useState(searchQuery);

    useEffect(() => {
        if (searchQuery === '' && inputValue !== '') {
            setInputValue('');
        }
    }, [searchQuery]);

    useEffect(() => {
        const timer = setTimeout(() => {
            if (inputValue !== searchQuery) {
                const newParams = new URLSearchParams(searchParams);
                if (inputValue.trim()) {
                    newParams.set('search', inputValue);
                } else {
                    newParams.delete('search');
                }
                setSearchParams(newParams, {replace: true});
            }
        }, 350);

        return () => clearTimeout(timer);
    }, [inputValue]);

    const handleDifficultyToggle = (value) => {
        const newParams = new URLSearchParams(searchParams);
        let updated;

        if (selectedDifficulties.includes(value)) {
            updated = selectedDifficulties.filter(item => item !== value);
        } else {
            updated = [...selectedDifficulties, value];
        }

        if (updated.length > 0) {
            newParams.set('difficulty', updated.join(','));
        } else {
            newParams.delete('difficulty');
        }

        setSearchParams(newParams);
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
                    <span>OnBeat</span>
                </Navbar.Brand>
            </Link>

            <Navbar.Toggle aria-controls="main-navbar"/>

            <Navbar.Collapse id="main-navbar">
                {showSearch && (
                    <Form className="d-flex mx-auto gap-3" style={{width: '420px'}}
                          onSubmit={(e) => e.preventDefault()}>

                        <Dropdown>
                            <Dropdown.Toggle variant="outline-secondary" id="difficulty-dropdown"
                                             className="text-light d-flex align-items-center gap-1">
                                <Filter size={14}/>
                            </Dropdown.Toggle>

                            <Dropdown.Menu className="bg-dark border-secondary p-2 shadow" style={{minWidth: '180px'}}>
                                <div className="text-muted small px-2 pb-1 border-bottom border-secondary mb-1">
                                    Filter by Difficulty
                                </div>
                                {DIFFICULTY_OPTIONS.map(option => {
                                    const isChecked = selectedDifficulties.includes(option.key);
                                    return (
                                        <div
                                            key={option.key}
                                            className="dropdown-item text-light bg-transparent px-2 py-1 rounded cursor-pointer"
                                            style={{cursor: 'pointer'}}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDifficultyToggle(option.key);
                                            }}
                                        >
                                            <FormCheck
                                                type="checkbox"
                                                id={`diff-${option.key}`}
                                                label={option.value}
                                                checked={isChecked}
                                                onChange={() => {
                                                }}
                                                className="user-select-none custom-checkbox text-light pointer-event-none"
                                                style={{cursor: 'pointer'}}
                                            />
                                        </div>
                                    );
                                })}
                            </Dropdown.Menu>
                        </Dropdown>
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
                    {/*<Button*/}
                    {/*    variant="primary"*/}
                    {/*    onClick={seedVideos}*/}
                    {/*    className="d-flex align-items-center gap-2 px-3 py-2 fw-semibold shadow-sm"*/}
                    {/*>*/}
                    {/*    <Upload size={16}/>*/}
                    {/*    <span>Seed</span>*/}
                    {/*</Button>*/}

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