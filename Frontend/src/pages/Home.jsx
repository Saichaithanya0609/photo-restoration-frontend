import Hero from "../components/HeroSection";
import Editor from "../components/Editor";

const Home = () => {
  return (
    <div className="home-page">
      <Hero />
      <Editor />
      <main>
        <section className="features">
          <h2>Why choose us?</h2>
          <div className="feature-grid">
            <article>
              <h3>Damage Repair</h3>
              <p>Remove scratches, tears, and dust from your treasured photos.</p>
            </article>
            <article>
              <h3>Colorization</h3>
              <p>Give black-and-white photos a vibrant, realistic finish.</p>
            </article>
            <article>
              <h3>Upscaling</h3>
              <p>Enhance image quality for print, digital sharing, and archival preservation.</p>
            </article>
          </div>
        </section>
      </main>
    </div>
  );
};

export default Home;
