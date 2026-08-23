import { 
  ShieldCheck, 
  Clock, 
  Database, 
  FileJson, 
  FileText, 
  Terminal, 
  CheckCircle,
  Activity,
  Bot,
  Download,
  BookMarked
} from 'lucide-react';
import React, { useEffect, useState } from 'react';

const RUN_STATS = [
  { label: "Pages Requested", value: "1–3", icon: FileText },
  { label: "Books Parsed", value: "60", icon: Database },
  { label: "Books Accepted", value: "60", icon: Activity },
  { label: "Validation", value: "0 failed", icon: CheckCircle },
];

const GUARANTEES = [
  {
    title: "Robots.txt Honored",
    description: "Parsed and respected all disallow rules from the target site prior to initialization.",
    icon: ShieldCheck,
  },
  {
    title: "Rate Limited",
    description: "Enforced the configured 500 ms minimum delay between network fetches.",
    icon: Clock,
  },
  {
    title: "Transparent Identification",
    description: "Requests identify themselves as FlyRank-PoliteScraper/1.0 with contact metadata.",
    icon: Bot,
  }
];

const LOGS = [
  { time: "clean", level: "INFO", message: "Pages 1–3 requested against books.toscrape.com" },
  { time: "clean", level: "EVID", message: "3 pages succeeded; 60 book records parsed and accepted" },
  { time: "clean", level: "SAFE", message: "robots.txt fetched once; 3 network page fetches; 500 ms floor configured" },
  { time: "warm", level: "EVID", message: "Immediate rerun: 3 cache hits; 0 network fetches; 60 accepted" },
  { time: "partial", level: "INFO", message: "Pages 1, 2, and unavailable page 9999 requested live" },
  { time: "partial", level: "WARN", message: "Page 9999 returned HTTP 404; pages 1–2 retained 40 valid records" },
  { time: "partial", level: "SUCC", message: "Partial-failure preservation confirmed; JSON and CSV written" },
];

const COVERAGE = [
  { module: "robots + User-Agent", percent: 100 },
  { module: "throttle + timeout", percent: 100 },
  { module: "cache + warm cache", percent: 100 },
  { module: "validation + output", percent: 100 },
];

function SectionCard({ title, children, icon: Icon, className = "" }: { title: string, children: React.ReactNode, icon?: any, className?: string }) {
  return (
    <section className={`bg-card border border-border p-6 rounded-md shadow-sm relative overflow-hidden ${className}`}>
      <div className="flex items-center gap-3 mb-6 pb-4 border-b border-border/60 relative z-10">
        {Icon && <Icon className="w-5 h-5 text-primary" />}
        <h3 className="font-serif text-lg text-foreground tracking-wide">{title}</h3>
      </div>
      <div className="relative z-10">
        {children}
      </div>
    </section>
  );
}

export default function Dashboard() {
  const [isLoaded, setIsLoaded] = useState(false);
  
  useEffect(() => {
    setIsLoaded(true);
  }, []);

  return (
    <div className="min-h-screen noise-bg selection:bg-primary/20 selection:text-primary pb-20 overflow-x-hidden">
      <div className={`max-w-5xl mx-auto pt-12 md:pt-20 px-6 transition-all duration-1000 ease-out ${isLoaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
        
        {/* Header */}
        <header className="border-b-2 border-foreground/10 pb-8 mb-10 flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <BookMarked className="w-5 h-5 text-primary" />
              <h2 className="text-xs font-mono tracking-widest text-muted-foreground uppercase">Field Report // 005</h2>
            </div>
            <h1 className="text-4xl md:text-5xl font-serif text-foreground leading-tight">
              Polite Scraper<br/>
              <span className="text-muted-foreground italic text-3xl md:text-4xl">Data Collection Mission</span>
            </h1>
          </div>
          <div className="flex items-center gap-4 border border-border bg-card p-2 md:p-3 rounded-md shadow-sm">
            <div className="px-3 py-1.5 bg-primary/10 text-primary border border-primary/20 rounded font-mono text-xs flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
              VERIFIED COMPLETED
            </div>
            <div className="text-xs font-mono text-muted-foreground pr-2 hidden md:block">
               2026-08-22 live run
            </div>
          </div>
        </header>

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10">
          
          {/* Left Column (Main Content) */}
          <div className="lg:col-span-8 space-y-10">
            
            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {RUN_STATS.map((s, i) => (
                <div 
                  key={s.label} 
                  className="bg-card border border-border p-5 rounded-md shadow-sm flex flex-col justify-between transition-transform duration-500 hover:-translate-y-1"
                  style={{ transitionDelay: `${i * 100}ms` }}
                >
                  <div className="flex items-center gap-2 mb-4 text-muted-foreground">
                    <s.icon className="w-4 h-4 text-secondary/70" />
                    <span className="font-mono text-[10px] uppercase tracking-wider">{s.label}</span>
                  </div>
                  <div className="font-serif text-2xl md:text-3xl text-foreground">
                    {s.value}
                  </div>
                </div>
              ))}
            </div>

            {/* Checkpoint Evidence Terminal */}
            <div className="bg-secondary text-secondary-foreground p-6 rounded-md shadow-inner border border-secondary/80 relative overflow-hidden">
              {/* Scanline subtle effect */}
              <div className="absolute inset-0 bg-[linear-gradient(transparent_50%,rgba(0,0,0,0.05)_50%)] bg-[length:100%_4px] pointer-events-none opacity-20"></div>
              
              <div className="flex items-center justify-between mb-6 pb-4 border-b border-secondary-foreground/10 relative z-10">
                <div className="flex items-center gap-2 text-secondary-foreground/70">
                  <Terminal className="w-4 h-4" />
                  <span className="font-mono text-xs uppercase tracking-widest">Process Log // Trace Evidence</span>
                </div>
                <div className="font-mono text-xs text-secondary-foreground/40">
                  session_id: 8f92a1
                </div>
              </div>
              
              <div className="space-y-2.5 font-mono text-sm relative z-10 h-[320px] overflow-y-auto pr-2 custom-scrollbar">
                {LOGS.map((log, i) => (
                  <div key={i} className="flex gap-4 group transition-colors hover:bg-white/5 rounded px-2 -mx-2 py-1">
                    <span className="text-secondary-foreground/40 shrink-0 w-20">{log.time}</span>
                    <span className={`shrink-0 w-14 font-semibold ${
                      log.level === 'INFO' ? 'text-blue-300/80' : 
                      log.level === 'EVID' ? 'text-accent' : 
                      log.level === 'SUCC' ? 'text-green-400' :
                      'text-secondary-foreground/40'
                    }`}>
                      [{log.level}]
                    </span>
                    <span className="text-secondary-foreground/90 break-words">
                      {log.message}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Target Details */}
            <SectionCard title="Target Analysis" icon={BookMarked}>
              <div className="prose prose-sm prose-p:font-sans prose-p:text-muted-foreground prose-headings:font-serif prose-a:text-primary max-w-none">
                <p>
                   The scraper ran against <strong>books.toscrape.com</strong>, a dedicated sandbox environment for web scraping validation.
                   The live clean-cache checkpoint requested catalogue pages 1, 2, and 3 and parsed 20 real book records per page.
                </p>
                <p>
                   All 60 records passed validation with no duplicates or validation failures. A warm-cache rerun served all three pages from disk, while a separate live request for page 9999 returned HTTP 404 without discarding the 40 valid records from pages 1 and 2.
                </p>
              </div>
            </SectionCard>
          </div>

          {/* Right Column (Meta & Outputs) */}
          <div className="lg:col-span-4 space-y-10">
            
            <SectionCard title="Safety Guarantees" icon={ShieldCheck}>
              <div className="space-y-6">
                {GUARANTEES.map((g) => (
                  <div key={g.title} className="flex gap-3 group">
                    <div className="mt-0.5 bg-muted group-hover:bg-primary/10 transition-colors p-2 rounded h-fit">
                      <g.icon className="w-4 h-4 text-secondary group-hover:text-primary transition-colors" />
                    </div>
                    <div>
                      <h4 className="font-sans font-medium text-sm text-foreground">{g.title}</h4>
                      <p className="font-sans text-xs text-muted-foreground mt-1 leading-relaxed">{g.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard title="Output Artifacts" icon={Download}>
              <div className="grid grid-cols-1 gap-3">
                <a href="#" onClick={e => e.preventDefault()} className="group flex items-center justify-between p-3 border border-border rounded hover:bg-primary hover:border-primary hover:text-primary-foreground transition-all duration-300">
                  <div className="flex items-center gap-3">
                    <FileText className="w-5 h-5 text-secondary group-hover:text-primary-foreground/80 transition-colors" />
                    <div>
                       <div className="font-sans font-medium text-sm">accepted_books.csv</div>
                       <div className="font-mono text-[10px] text-muted-foreground group-hover:text-primary-foreground/60 mt-0.5 transition-colors">8.6 KB · 60 rows</div>
                    </div>
                  </div>
                  <div className="text-[10px] font-mono text-primary group-hover:text-primary-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                    DOWNLOAD
                  </div>
                </a>
                <a href="#" onClick={e => e.preventDefault()} className="group flex items-center justify-between p-3 border border-border rounded hover:bg-primary hover:border-primary hover:text-primary-foreground transition-all duration-300">
                  <div className="flex items-center gap-3">
                    <FileJson className="w-5 h-5 text-secondary group-hover:text-primary-foreground/80 transition-colors" />
                    <div>
                       <div className="font-sans font-medium text-sm">accepted_books.json</div>
                       <div className="font-mono text-[10px] text-muted-foreground group-hover:text-primary-foreground/60 mt-0.5 transition-colors">15.6 KB · 60 records</div>
                    </div>
                  </div>
                  <div className="text-[10px] font-mono text-primary group-hover:text-primary-foreground opacity-0 group-hover:opacity-100 transition-opacity">
                    DOWNLOAD
                  </div>
                </a>
              </div>
            </SectionCard>

            <SectionCard title="Test Coverage" icon={CheckCircle}>
              <div className="space-y-5">
                <div>
                  <div className="flex items-end justify-between mb-2">
                     <div className="font-sans font-medium text-sm text-foreground">Automated suite</div>
                     <div className="font-mono text-xl text-primary">10 / 10</div>
                  </div>
                  <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                     <div className="bg-primary h-full rounded-full transition-all duration-1000 ease-out" style={{ width: isLoaded ? '100%' : '0%' }}></div>
                  </div>
                </div>
                
                <div className="pt-4 border-t border-border/60 space-y-3">
                  {COVERAGE.map((c) => (
                    <div key={c.module} className="flex justify-between items-center text-sm group">
                      <span className="font-mono text-[10px] text-muted-foreground group-hover:text-foreground transition-colors">{c.module}</span>
                      <div className="flex items-center gap-2">
                        <div className="w-12 h-1 bg-muted rounded-full overflow-hidden hidden sm:block">
                          <div className="bg-secondary h-full rounded-full transition-all duration-1000 ease-out" style={{ width: isLoaded ? `${c.percent}%` : '0%' }}></div>
                        </div>
                        <span className="font-mono text-[10px] font-medium">{c.percent}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </SectionCard>

          </div>
        </div>
      </div>
    </div>
  );
}
