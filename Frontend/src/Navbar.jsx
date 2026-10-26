import { NavLink } from "react-router-dom";

const Navbar = () => {
  return (
    <nav className="site-nav" aria-label="Main navigation">
      <NavLink to="/">
        <span>Home</span>
      </NavLink>
      <NavLink to="/about">
        <span>About</span>
      </NavLink>
      <NavLink to="/features">
        <span>Features</span>
      </NavLink>
      <NavLink to="/work">
        <span>Our Work</span>
      </NavLink>
    </nav>
  );
};

export default Navbar;
