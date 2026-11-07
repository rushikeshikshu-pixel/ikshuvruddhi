import { ArrowUpRight, ArrowRight, Satellite, FlaskConical, Sprout, Layers, ShieldCheck, ChevronRight } from "lucide-react";
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
          <a href="#workflow">How it works</a>
          <a href="#science">Our approach</a>
        </nav>
        <a className="nav-login" href="/login">
          Mill login <ArrowUpRight size={16} />
        </a>
      </header>

      <main>
        {/* HERO SECTION - EXACT EXISTING UI STRUCTURE */}
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
              Bring your cane landscape into focus. One workspace for sugar mills to connect 26,000+ cadastral plots, multi-sensor radar &amp; optical telemetry, and factory laboratory polarimeter quality.
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
                <strong>97.65%</strong>
                <span>Brix Accuracy (&plusmn;0.38&deg;Bx)</span>
              </div>
              <div>
                <strong>96.64%</strong>
                <span>Pol Accuracy (&plusmn;0.47%)</span>
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
                <Sprout size={22} />
              </div>
              <div>
                <small>SMART 54 INVERSION ENGINE</small>
                <strong>Standing &amp; Delivered Sucrose</strong>
              </div>
              <ArrowUpRight size={20} />
            </div>
            <div className="map-scale">
              <span className="scale-bar" />
              Gangamai Sugar Command Area <span>19.5° N · 75.3° E</span>
            </div>
          </div>
        </section>

        {/* CAPABILITY STRIP */}
        <div className="capability-strip">
          <div className="wrap">
            <span>BUILT AROUND YOUR MILL</span>
            <span><Layers size={18} /> Plot intelligence</span>
            <span><Satellite size={18} /> Satellite context</span>
            <span><FlaskConical size={18} /> Cane quality</span>
            <span><Sprout size={18} /> Harvest planning</span>
          </div>
        </div>

        {/* SECTION 1: THE PLATFORM */}
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
              <div className="feature-icon"><Layers /></div>
              <h3>Your plots, connected.</h3>
              <p>
                Import the mill register, search by plot or village, and keep crop age, variety and field area together with real-time audit flags.
              </p>
              <div className="mini-register">
                <div>
                  <span>Plot</span>
                  <span>Village</span>
                  <span>Variety</span>
                </div>
                <div>
                  <b>26989</b>
                  <span>Joharapur (Dattatraya Wasti)</span>
                  <span className="pill">CO-265</span>
                </div>
                <div>
                  <b>23609</b>
                  <span>Ambad (Gaikwad Subhash)</span>
                  <span className="pill">CO-265</span>
                </div>
                <div>
                  <b>17341</b>
                  <span>Paithan (Khedkar Vikram)</span>
                  <span className="pill">CO-265</span>
                </div>
                <small>Audited Gangamai command area plots &bull; 06-Nov 2026</small>
              </div>
            </article>

            <article className="feature-card">
              <div className="feature-icon"><Satellite /></div>
              <h3>See the observation.</h3>
              <p>
                Search Copernicus Sentinel-2C optical or Sentinel-1 SAR radar scenes by field and date. Keep cloud screening, valid-pixel coverage and radar stalk volume visible.
              </p>
              <div className="orbit-graphic">
                <Satellite size={31} />
                <i /><i /><i />
                <span className="observation-chip">Copernicus 2C &bull; Dual-Pol SAR &bull; 10m</span>
              </div>
            </article>

            <article className="feature-card">
              <div className="feature-icon"><FlaskConical /></div>
              <h3>Quality, with context.</h3>
              <p>
                Model standing field sucrose alongside factory-gate delivered sugar. Account for cut-to-crush transit invertase decay and moisture evaporation across transport distances.
              </p>
              <div className="quality-mini">
                <span>LAB MEASUREMENTS (10 BATCHES)</span>
                <div>
                  <strong>Pol: 96.64%</strong>
                  <b>Brix: 97.65%</b>
                  <em>CCS: 95.77%</em>
                </div>
                <small>0.38&deg;Bx MAE &bull; Validated on certified Gangamai mill laboratory slips.</small>
              </div>
            </article>
          </div>
        </section>

        {/* SECTION 2: A CONNECTED WORKFLOW */}
        <section id="workflow" className="workflow-section">
          <div className="wrap">
            <div className="section-head">
              <div>
                <div className="eyebrow">02 / A CONNECTED WORKFLOW</div>
                <h2>
                  From the field register<br />
                  to the next harvest.
                </h2>
              </div>
              <a href="/demo" className="text-link light">
                Open the interactive demo <ArrowUpRight size={18} />
              </a>
            </div>
            <div className="steps">
              <article>
                <span>01</span>
                <h3>Bring your mill data.</h3>
                <p>
                  Create your workspace and import plot records from CSV. Connect survey numbers, farmer accounts, and planting dates seamlessly.
                </p>
              </article>
              <article>
                <span>02</span>
                <h3>Add the evidence.</h3>
                <p>
                  Fetch multi-satellite observations and cross-reference laboratory refractometer samples against each plot with certified acquisition dates.
                </p>
              </article>
              <article>
                <span>03</span>
                <h3>Plan with confidence.</h3>
                <p>
                  Filter plots by sucrose maturity tiers, detect diverted tonnage, and create optimal rapid harvest schedules that maximize factory sugar recovery.
                </p>
              </article>
            </div>
          </div>
        </section>

        {/* SECTION 3: EVIDENCE BEFORE ESTIMATES */}
        <section id="science" className="science-section wrap">
          <div className="science-mark">
            <span>IK</span>
            <span className="mono">OBSERVE &rarr; VALIDATE &rarr; DECIDE</span>
          </div>
          <div>
            <div className="eyebrow">03 / EVIDENCE BEFORE ESTIMATES</div>
            <h2>
              Intelligence needs<br />
              <em>ground truth.</em>
            </h2>
            <p>
              Cloud screening, dated biophysical observations and independent factory lab validation are central to useful cane intelligence. Every estimate travels with verifiable physical ground truth.
            </p>
            <ul className="principles">
              <li><ShieldCheck size={19} /> Physical mill laboratory validation (0.38&deg;Bx MAE)</li>
              <li><Satellite size={19} /> Transparent Copernicus Sentinel-2C telemetry and 100% cloud screening</li>
              <li><FlaskConical size={19} /> Laboratory refractometer &amp; polarimeter results remain the ground reference</li>
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
            <p>Give your mill a workspace built for the way cane is grown, measured and harvested.</p>
            <a className="button primary" href="/login">
              Sign in and set up your mill <ArrowUpRight size={19} />
            </a>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer className="site-footer wrap">
        <Brand />
        <span>Field intelligence. Mill perspective.</span>
        <div>
          <a href="/privacy">Privacy</a>
          <a href="/login">Mill login</a>
        </div>
        <small>&copy; {new Date().getFullYear()} Ikshu Intelligence</small>
      </footer>
    </>
  );
}
