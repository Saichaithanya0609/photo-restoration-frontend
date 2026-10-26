import "../App.css";

const Hero = () => {
  return (
    <div>
      <section className="hero-banner">
        <div className="hero-copy">
          <div className="hero-badge">
            <span aria-hidden="true">{String.fromCodePoint(0x26a1)}</span>{" "}
            AI-Powered Enhancement v2.4
          </div>
          <h1>
            Photo <span>Restoration and Enhancement System</span>
          </h1>
          <p>
            Bring your old, faded and noisy photographs back to life using
            advanced Digital Image Processing techniques and neural network
            enhancement.
          </p>
        </div>

        {/* Hero Right Graphic (Polaroids) */}
        <div className="hero-visual">
          <div className="photo-pair">
            {/* Old Photo Polaroid */}
            <div className="polaroid polaroid-before">
              <img
                src="https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&q=40&w=90"
                alt="Old faded"
                className="polaroid-image faded-image"
              />
              <div className="photo-caption">1978.jpg</div>
            </div>

            {/* Transition Arrow */}
            <div className="photo-arrow" aria-hidden="true">
              <span>{String.fromCodePoint(0x2192)}</span>
            </div>

            {/* Restored Photo Polaroid */}
            <div className="polaroid polaroid-after">
              <img
                src="https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&q=80&w=300"
                alt="Restored"
                className="polaroid-image"
              />
              <div className="photo-caption restored-caption">Enhanced.jpg</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Hero;
