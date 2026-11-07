import { 
  ArrowUpRight, 
  ArrowRight, 
  Satellite, 
  FlaskConical, 
  Sprout, 
  Layers, 
  ShieldCheck, 
  ChevronRight, 
  Activity, 
  Radar, 
  Cpu, 
  Truck, 
  CheckCircle2, 
  AlertTriangle 
} from "lucide-react";
import FieldMap from "./ui/field-map";
import Brand from "./ui/brand";

export default function Home() {
  return (
    <>
      <header className="site-nav wrap">
        <a href="/" aria-label="Ikshu Intelligence home">
          <Brand />
        </a>
        <nav aria-label="Main navigation">
          <a href="#platform">Platform</a>
          <a href="#engines">Smart 54 Engine</a>
          <a href="#audit">Lifecycle Audit</a>
          <a href="#workflow">Workflow</a>
          <a href="#science">Our approach</a>
        </nav>
        <a className="nav-login" href="/login">
          Mill login <ArrowUpRight size={16} />
        </a>
      </header>

      <main>
        {/* HERO SECTION */}
        <section className="hero wrap">
          <div className="hero-copy">
            <div className="eyebrow">
              <span className="status-dot" /> COPERNICUS SENTINEL-2C &bull; 06-NOV 11:03 AM IST
            </div>
            <h1>
              Every field.<br />
              A clearer <em>future.</em>
            </h1>
            <p>
              Bring your cane landscape into focus. One enterprise workspace connecting 26,000+ cadastral plots, multi-sensor radar &amp; optical telemetry, and factory laboratory polarimeter quality.
            </p>
            <div className="hero-actions">
              <a className="button primary" href="/login">
                Enter your mill workspace <ArrowUpRight size={18} />
              </a>
              <a className="text-link" href="/demo">
                Explore the platform <ArrowRight size={17} />
              </a>
            </div>
            <div className="hero-metrics">
              <div>
                <strong>26,471</strong>
                <span>Plots Mapped (23,276 Ha)</span>
              </div>
              <div>
                <strong>94.99%</strong>
                <span>Brix Accuracy (&plusmn;0.83&deg;Bx)</span>
              </div>
              <div>
                <strong>92.27%</strong>
                <span>Pol Accuracy (&plusmn;1.05%)</span>
              </div>
              <div>
                <strong>1,880</strong>
                <span>Audit Anomalies Flagged</span>
              </div>
            </div>
            <div className="hero-foot">
              <ShieldCheck size={17} />
              <span>Physically validated on Gangamai Sugar factory lab batches (05-Nov &amp; 06-Nov crushes).</span>
            </div>
          </div>

          <div className="hero-visual">
            <div className="visual-top">
              <span>
                <span className="status-dot" /> THE CANE LANDSCAPE
              </span>
              <span className="mono">IKSHU / 54-PARAM FIELD VIEW</span>
            </div>
            <FieldMap />
            <div className="map-float">
              <div className="float-icon">
                <Radar size={22} />
              </div>
              <div>
                <small>SENTINEL-2C &bull; C-SAR FUSION</small>
                <strong>Smart 54-Parameter Inversion</strong>
              </div>
              <ArrowUpRight size={20} />
            </div>
            <div className="map-scale">
              <span className="scale-bar" />
              Live Cadastral Telemetry <span>19.52&deg; N &bull; 75.02&deg; E</span>
            </div>
          </div>
        </section>

        {/* CAPABILITY STRIP */}
        <div className="capability-strip">
          <div className="wrap">
            <span>BUILT AROUND YOUR MILL</span>
            <span><Layers size={18} /> 26,471 Cadastral Plots</span>
            <span><Radar size={18} /> SAR C-Band Penetration</span>
            <span><Cpu size={18} /> Smart 54 AI Model</span>
            <span><Truck size={18} /> Cut-to-Crush Transit Loss</span>
            <span><FlaskConical size={18} /> 95% Lab Accuracy</span>
          </div>
        </div>

        {/* 01. PLATFORM SECTION */}
        <section id="platform" className="platform-section wrap">
          <div className="section-head">
            <div>
              <div className="eyebrow">01 / THE PLATFORM</div>
              <h2>
                The bigger picture.<br />
                <em>The details that matter.</em>
              </h2>
            </div>
            <p>
              Move from scattered spreadsheets to a structured view of your command area, with the evidence behind every decision.
            </p>
          </div>

          <div className="feature-grid">
            <article className="feature-card wide">
              <div className="feature-icon">
                <Layers />
              </div>
              <h3>Your plots, connected.</h3>
              <p>
                Import the mill register, search by plot or village, and keep crop age, variety maturity group, and cadastral boundary area unified across 22 circles.
              </p>
              <div className="mini-register">
                <div>
                  <span>Plot</span>
                  <span>Village</span>
                  <span>Variety</span>
                </div>
                <div>
                  <b>IK-142</b>
                  <span>Babhaleshwar</span>
                  <span className="pill">CO-86032 (18.4&deg;Bx)</span>
                </div>
                <div>
                  <b>IK-17341</b>
                  <span>Shingave</span>
                  <span className="pill">Suru (16.9&deg;Bx)</span>
                </div>
                <div>
                  <b>IK-8082</b>
                  <span>Juni Khirdi</span>
                  <span className="pill">Waterlogged (15.4&deg;Bx)</span>
                </div>
                <small>Calibrated mill register &bull; 26,471 active parcels</small>
              </div>
            </article>

            <article className="feature-card">
              <div className="feature-icon">
                <Satellite />
              </div>
              <h3>See the observation.</h3>
              <p>
                Continuous surveillance using Copernicus Sentinel-2C optical and Sentinel-1 C-SAR radar. All-weather cloud piercing guarantees uninterrupted crop monitoring.
              </p>
              <div className="orbit-graphic">
                <Satellite size={31} />
                <i />
                <i />
                <i />
                <span className="observation-chip">06-Nov Overpass &bull; 10m GSD &bull; C-SAR Dual-Pol</span>
              </div>
            </article>

            <article className="feature-card">
              <div className="feature-icon">
                <FlaskConical />
              </div>
              <h3>Quality, with context.</h3>
              <p>
                Record measured Pol, Brix, Purity, and CCS. Compare dates and keep physical polarimeter laboratory measurements strictly synced with model forecasts.
              </p>
              <div className="quality-mini">
                <span>MILL LAB BENCHMARK</span>
                <div>
                  <strong>Pol: 92.3%</strong>
                  <b>Brix: 95.0%</b>
                  <em>CCS: 89.7%</em>
                </div>
                <small>Validated across blind mill crushes (05 &amp; 06 Nov 2026).</small>
              </div>
            </article>
          </div>
        </section>

        {/* 02. SMART 54 HIERARCHICAL ENGINE */}
        <section id="engines" className="platform-section wrap" style={{ paddingTop: "20px" }}>
          <div className="section-head">
            <div>
              <div className="eyebrow">02 / SMART 54 HIERARCHICAL AI</div>
              <h2>
                Biophysical Priors.<br />
                <em>Orthogonal Reality.</em>
              </h2>
            </div>
            <p>
              Moving beyond flat single-index NDVI heuristics into a decoupled two-stage physical learning engine that captures true stalk chemistry.
            </p>
          </div>

          <div className="feature-grid">
            <article className="feature-card">
              <div className="feature-icon">
                <Cpu />
              </div>
              <h3>Two-Stage Hierarchical Residuals</h3>
              <p>
                Stage 1 anchors biological potential using 10 physiological invariants. Stage 2 applies an asymmetric clamping envelope [-2.8&deg;, +1.2&deg;Bx] across 44 radar and terrain features to prevent unphysical hallucinations.
              </p>
            </article>

            <article className="feature-card">
              <div className="feature-icon">
                <Truck />
              </div>
              <h3>Cut-to-Crush Staling Kinetics</h3>
              <p>
                First remote sensing architecture to decouple standing field sucrose from delivered juice. Accounts for invertase enzyme degradation and evaporation over transit hauls up to 129 km and 28+ hours.
              </p>
            </article>

            <article className="feature-card">
              <div className="feature-icon">
                <Radar />
              </div>
              <h3>Resolving the Green-Leaf Paradox</h3>
              <p>
                Couples DEM Topographic Wetness Index (TWI) with C-SAR dielectric backscatter to detect root waterlogging that traps Brix below 15&deg;Bx despite lush green leaves (NDVI &gt; 0.75).
              </p>
            </article>
          </div>
        </section>

        {/* 03. CADASTRAL LIFECYCLE AUDIT (SLI ENGINE) */}
        <section id="audit" className="workflow-section">
          <div className="wrap">
            <div className="section-head">
              <div>
                <div className="eyebrow">03 / SATELLITE LIFECYCLE IDENTIFIER</div>
                <h2>
                  Cadastral Integrity.<br />
                  <em>Zero Ghost Cane.</em>
                </h2>
              </div>
              <a href="/demo" className="text-link light">
                Open Cadastral Audit Console <ArrowUpRight size={18} />
              </a>
            </div>

            <div className="steps">
              <article>
                <span>24,591</span>
                <h3>Clean Biological Lifecycle</h3>
                <p>
                  92.90% of command plots verified with normal growth phenology, healthy stalk density, and expected sucrose accumulation curves.
                </p>
              </article>

              <article>
                <span>1,880</span>
                <h3>Discrepancies Flagged (7.10%)</h3>
                <p>
                  Automatically detected 1,295 stunted canopy deficits, 242 Suru morphology plots mislabeled as Khodwa in survey books, and 340 date errors with zero manual field visits.
                </p>
              </article>

              <article>
                <span>Top 500</span>
                <h3>Priority Harvest Queue</h3>
                <p>
                  Identifies peak ripening plots (18.5&deg;Bx+) for front-loaded crushing while screening out 1,205 early-season low-Pol plots (&le; 13%) to protect mill recovery.
                </p>
              </article>
            </div>
          </div>
        </section>

        {/* 04. WORKFLOW SECTION */}
        <section id="workflow" className="workflow-section" style={{ background: "transparent" }}>
          <div className="wrap">
            <div className="section-head">
              <div>
                <div className="eyebrow">04 / A CONNECTED WORKFLOW</div>
                <h2>
                  From the field register<br />
                  to the next harvest.
                </h2>
              </div>
              <a href="/demo" className="text-link">
                Open the interactive demo <ArrowUpRight size={18} />
              </a>
            </div>

            <div className="steps">
              <article>
                <span>01</span>
                <h3>Bring your mill data.</h3>
                <p>
                  Import plot registers, Gat numbers, and walked mobile GPS traces. Clean and reconcile cadastral boundaries directly with MahaBhuNaksha records.
                </p>
              </article>

              <article>
                <span>02</span>
                <h3>Add satellite &amp; lab evidence.</h3>
                <p>
                  Ingest Sentinel-2C optical and Sentinel-1 radar observations. Pair with factory weighbridge core sampling polarimeter measurements.
                </p>
              </article>

              <article>
                <span>03</span>
                <h3>Dispatch with confidence.</h3>
                <p>
                  Generate 5-day daily crushing schedules (10,000 TCD capacity-balanced) and export cryptographically verified QR harvest chits.
                </p>
              </article>
            </div>
          </div>
        </section>

        {/* 05. EVIDENCE BEFORE ESTIMATES */}
        <section id="science" className="science-section wrap">
          <div className="science-mark">
            <span>IK</span>
            <span className="mono">OBSERVE &rarr; VALIDATE &rarr; DECIDE</span>
          </div>
          <div>
            <div className="eyebrow">05 / EVIDENCE BEFORE ESTIMATES</div>
            <h2>
              Intelligence needs<br />
              <em>ground truth.</em>
            </h2>
            <p>
              Cloud screening, dated satellite overpasses, and blind factory lab validation are central to useful cane intelligence. Our models are grounded in physics and verified on industrial crushing batches.
            </p>
            <ul className="principles">
              <li>
                <ShieldCheck size={19} /> Physically validated: 94.99% Brix MAE (&plusmn;0.835&deg;Bx)
              </li>
              <li>
                <Satellite size={19} /> Transparent Copernicus Sentinel-2C and Sentinel-1 C-SAR telemetry
              </li>
              <li>
                <FlaskConical size={19} /> Factory polarimeter laboratory refractions remain the reference
              </li>
            </ul>
            <a href="/demo" className="text-link">
              See how data is presented <ChevronRight size={18} />
            </a>
          </div>
        </section>

        {/* CTA SECTION */}
        <section className="cta-section wrap">
          <div>
            <div className="eyebrow">YOUR NEXT SEASON STARTS HERE</div>
            <h2>
              More clarity.<br />
              <em>From cane to mill.</em>
            </h2>
          </div>
          <div>
            <p>
              Give your mill an enterprise operational workspace built for the way sugarcane is grown, measured, transported, and crushed.
            </p>
            <a className="button primary" href="/login">
              Sign in and set up your mill <ArrowUpRight size={19} />
            </a>
          </div>
        </section>
      </main>

      <footer className="site-footer wrap">
        <Brand />
        <span>Field intelligence. Mill perspective.</span>
        <div>
          <a href="/privacy">Privacy</a>
          <a href="/login">Mill login</a>
        </div>
        <small>&copy; {new Date().getFullYear()} Ikshu Intelligence Inc.</small>
      </footer>
    </>
  );
}
