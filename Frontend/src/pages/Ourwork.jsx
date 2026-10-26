const projects = [
  {
    title: "Vintage Portrait Restoration",
    category: "Portraits",
    description:
      "Restored faded facial details, repaired scratches, and enhanced contrast for a timeless family portrait.",
    image:
      "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Wedding Photo Revival",
    category: "Events",
    description:
      "Color correction and damage repair brought new life to an old wedding album image.",
    image:
      "https://images.unsplash.com/photo-1520854221256-17451cc331bf?auto=format&fit=crop&w=900&q=80",
  },
  {
    title: "Old Film Enhancement",
    category: "Archives",
    description:
      "Cleanup of dust, stains, and softness improved the clarity of a cherished historical photograph.",
    image:
      "https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?auto=format&fit=crop&w=900&q=80",
  },
];

export default function Ourwork() {
  return (
    <section className="work-page">
      <div className="work-container">
        <header className="work-header">
          <p className="work-eyebrow">Our Work</p>
          <h1>Photo Restoration Projects</h1>
          <p className="work-subtitle">
            We restore treasured memories by repairing age, damage, and fading
            while preserving the original emotion and story in every image.
          </p>
        </header>

        <div className="work-grid">
          {projects.map((project) => (
            <article key={project.title} className="work-card">
              <img
                src={project.image}
                alt={project.title}
                className="work-image"
              />
              <div className="work-card-content">
                <span className="work-category">{project.category}</span>
                <h2>{project.title}</h2>
                <p className="work-card-text">{project.description}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
