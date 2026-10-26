import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./App.css";
import Home from "./pages/Home";
import About from "./pages/About";
import Features from "./pages/Features";
import OurWork from "./pages/Ourwork";
import Navbar from "./Navbar";

const App = () => {
  const router = createBrowserRouter([
    {
      path: "/",
      element: (
        <div>
          <Navbar />
          <Home />
        </div>
      ),
    },
    {
      path: "/about",
      element: (
        <div>
          <Navbar />
          <About />
        </div>
      ),
    },
    {
      path: "/features",
      element: (
        <div>
          <Navbar />
          <Features />
        </div>
      ),
    },
    {
      path: "/work",
      element: (
        <div>
          <Navbar />
          <OurWork />
        </div>
      ),
    },
  ]);

  return <RouterProvider router={router} />;
};

export default App;
