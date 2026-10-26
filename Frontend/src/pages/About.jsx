const About = () => {
  return (
    <div className="about-page">
      <section className="about-hero">
        <h1>About Photo Restoration</h1>
        <p>
          We help bring old, damaged, and faded memories back to life with
          modern restoration tools and careful digital enhancement.
        </p>
      </section>

      <section className="about-content">
        <div className="about-card">
          <h2>Our Mission</h2>
          <p>
            Our mission is to preserve personal history by restoring photos with
            detail, care, and authenticity.
          </p>
        </div>

        <div className="about-card">
          <h2>What We Do</h2>
          <p>
            We remove scratches, improve clarity, restore color, and revive old
            images for families, artists, and collectors.
          </p>
        </div>

        <div className="about-card">
          <h2>Why It Matters</h2>
          <p>
            Every photograph tells a story. We believe those memories deserve to
            be preserved beautifully for generations to come.
          </p>
        </div>
      </section>
    </div>
  );
};

export default About;
