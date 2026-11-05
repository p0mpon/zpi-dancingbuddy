import React, { useState } from 'react';
import { Container, Card, Form, Button, Alert } from 'react-bootstrap';
import {Link, useNavigate} from 'react-router-dom';
import {useAuth} from "../../context/AuthContext";

export function LoginPage() {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    
    const {login} = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        
        if (!email || !password) {
            setError('Fill in all fields');
        }
        try {
            await login({ email, password });
            navigate('/');
        } catch (err) {
            setError("Login invalid");
        }
    };

    return (
        <Container className="d-flex align-items-center justify-content-center py-5">
            <Card bg="black" text="light" className="border-secondary shadow p-3"
                  style={{maxWidth: '420px', width: '100%'}}>
                <Card.Body>
                    <div className="text-center mb-4">
                        <h3 className="fw-bold">Sign in</h3>
                    </div>

                    {error && <Alert variant="danger" className="py-2 small">{error}</Alert>}

                    <Form onSubmit={handleSubmit}>
                        <Form.Group className="mb-3" controlId="loginEmail">
                            <Form.Label className="text-muted-light small" column>Email Address</Form.Label>
                            <Form.Control
                                // type="email"
                                placeholder="name@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Form.Group className="mb-4" controlId="loginPassword">
                            <Form.Label className="text-muted-light small" column>Password</Form.Label>
                            <Form.Control
                                type="password"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="bg-dark text-light border-secondary"
                            />
                        </Form.Group>

                        <Button variant="primary" type="submit" className="w-100 fw-bold py-2 mb-3">
                            Sign In
                        </Button>
                    </Form>

                    <div className="text-center text-muted-light small">
                        Don't have an account?{' '}
                        <Link to="/register" className="text-primary text-decoration-none fw-semibold">
                            Register
                        </Link>
                    </div>
                </Card.Body>
            </Card>
        </Container>
    );
}