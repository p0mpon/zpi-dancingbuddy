import React from 'react';
import {Button, Row, Col, Card, Nav, Tab, Image} from 'react-bootstrap';
import {Film, GearFill} from "react-bootstrap-icons";
import {useAuth} from "../context/AuthContext";

export default function UserDashboard () {
    const { user } = useAuth();
    return (
        <>
            <Card bg="black" text="light" className="border-secondary shadow-sm mb-4">
                <Card.Body className="p-4">
                    <Row className="align-items-center g-3">
                        <Col xs="auto">
                            <div
                                className="rounded-circle border border-primary border-3 overflow-hidden d-flex align-items-center justify-content-center shadow"
                                style={{ width: '96px', height: '96px' }}
                            >
                                <Image
                                    src={user.avatar}
                                    alt={user.username}
                                    fluid
                                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                />
                            </div>
                        </Col>

                        <Col>
                            <div className="d-flex align-items-center gap-2 mb-1">
                                <h3 className="fw-bold mb-0">{user.username}</h3>
                            </div>
                            <p className="text-muted-light mb-2 small">{user.email}</p>
                        </Col>
                    </Row>
                </Card.Body>
            </Card>
            

            <Tab.Container defaultActiveKey="my-videos">
                <Card bg="black" text="light" className="border-secondary">
                    <Card.Header className="border-secondary bg-transparent p-0">
                        <Nav variant="tabs" className="border-bottom-0">
                            <Nav.Item>
                                <Nav.Link eventKey="my-videos" className="text-light border-0 py-3 px-4 d-flex align-items-center gap-2">
                                    <Film size={16} /> My Videos
                                </Nav.Link>
                            </Nav.Item>
                            <Nav.Item>
                                <Nav.Link eventKey="settings" className="text-light border-0 py-3 px-4 d-flex align-items-center gap-2">
                                    <GearFill size={16} /> Account Settings
                                </Nav.Link>
                            </Nav.Item>
                        </Nav>
                    </Card.Header>

                    <Card.Body className="p-4">
                        <Tab.Content>
                            <Tab.Pane eventKey="my-videos">
                                <div className="text-center py-5 text-muted-light">
                                    <Film size={40} className="mb-2" />
                                    <p className="mb-0">Your uploaded videos will appear here.</p>
                                </div>
                            </Tab.Pane>

                            <Tab.Pane eventKey="settings">
                                <h5 className="fw-bold text-light mb-3">Account Preferences</h5>
                                <p className="text-muted-light small mb-4">Manage your profile details and preferences.</p>

                                <div className="d-flex flex-column gap-3 max-w-md">
                                    <div>
                                        <label htmlFor="user" className="form-label text-muted-light small mb-1">Username</label>
                                        <input
                                            id="user"
                                            type="text"
                                            defaultValue={user.username}
                                            className="form-control bg-dark text-light border-secondary"
                                        />
                                    </div>

                                    <div>
                                        <label htmlFor="email" className="form-label text-muted-light small mb-1">Email</label>
                                        <input
                                            id="email"
                                            type="email"
                                            defaultValue={user.email}
                                            className="form-control bg-dark text-light border-secondary"
                                        />
                                    </div>

                                    <div className="pt-2">
                                        <Button variant="primary" size="sm">Save Changes</Button>
                                    </div>
                                </div>
                            </Tab.Pane>
                        </Tab.Content>
                    </Card.Body>
                </Card>
            </Tab.Container>
        </>
    )}