import React from 'react';
import Container from 'react-bootstrap/Container';
import Nav from 'react-bootstrap/Nav';
import Navbar from 'react-bootstrap/Navbar';
import NavDropdown from 'react-bootstrap/NavDropdown';
import Row from 'react-bootstrap/Row';
import Col from 'react-bootstrap/Col';
import logo from './logo.png';
import SearchBar from './SearchBar';

function HeaderBar() {
  return ( /*purple = 712cf9 */
    <>
      <style type="text/css">
        {`    
      .btn-infini {
        background-color: #ec424c !important;
        color: white !important;
        border-radius: 6px;
      }

      .btn-infini:hover {
        background-color: #b42a4c !important;  
      }

      .btn-xxl {
        padding: .5rem 1.2rem;
        font-size: 1rem;
      } 
      .navbar-infini {
        background-color: #18141a !important;
        color: black !important;
        border-bottom: 1px solid !important;
        border-color: #b42a4c !important
      }

      .navbar-infini .navbar-brand {
        color: white !important;
      }

      .navbar-infini .navbar-toggler,
      .navbar-infini .nav-link {
        color: #8c8a8d !important;
      }
      `}
      </style>
       <Navbar variant="infini" expand="lg" fixed="top">
          <Container>
            <Navbar.Brand href="/">
              <img
                src={logo}
                width="30"
                height="30"
                className="d-inline-block align-top"
                alt="Logo"
              />
              {' '}Infiniportal
            </Navbar.Brand>
            <Nav className="me-auto">
            <Row>
              <Col>
                <Nav.Link href="/leaderboard">Leaderboard</Nav.Link>
              </Col>
              <Col>
                <NavDropdown data-bs-theme="dark" title="Discord" id="basic-nav-dropdown">
                  <NavDropdown.Item href="https://discord.com/oauth2/authorize?client_id=1233991850470277130&scope=bot&permissions=1342598160">Discord Bot</NavDropdown.Item>
                  <NavDropdown.Item href="/terms">Terms of Conditions</NavDropdown.Item>
                  <NavDropdown.Item href="/privacy">Privacy Policy</NavDropdown.Item>
                </NavDropdown>
              </Col>
            </Row>
          </Nav>
        <>
          <Navbar.Toggle aria-controls="basic-navbar-nav" />
          <Navbar.Collapse id="basic-navbar-nav" className="justify-content-sm-end">
            <SearchBar/>
          </Navbar.Collapse>
        </>
        </Container>
      </Navbar>
      </>
    );
}

export default HeaderBar;