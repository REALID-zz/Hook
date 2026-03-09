export type Id = string;

export type CardProfile = {
  displayName: string;
  tagline: string;
  contact?: { email?: string; wechat?: string };
  status: 'online' | 'focus' | 'offline';
  mission?: string;
  stack?: string;
  collab?: string;
};

export type Greeting = {
  id: Id;
  createdAt: number;
  venue: string;
  from: string;
  message: string;
};

export type TextBlock = {
  key: string;
  updatedAt: number;
  text: string;
};

export type HelpRequest = {
  id: Id;
  createdAt: number;
  expiresAt: number;
  venue: string;
  title: string;
  detail: string;
  urgency: 'low' | 'med' | 'high';
};

export type PublicPost = {
  id: Id;
  createdAt: number;
  venue: string;
  category: 'announcement' | 'lostfound' | 'community' | 'robot4s';
  title: string;
  detail: string;
};

export type EmergencyCase = {
  id: Id;
  createdAt: number;
  venue: string;
  type:
    | 'missing_child'
    | 'missing_elder'
    | 'missing'
    | 'violence_risk'
    | 'medical'
    | 'fire'
    | 'disaster'
    | 'fraud'
    | 'other';
  reason: 'witness' | 'self' | 'proxy' | 'online_lead';
  risk: 'low' | 'medium' | 'high';
  summary: string;
  details: string;
};

export type AppState = {
  venue: string;
  profile: CardProfile;
  greetings: Greeting[];
  texts: Record<string, TextBlock>;
  help: HelpRequest[];
  posts: PublicPost[];
  emergencies: EmergencyCase[];
};

const KEY = 'ahelpis-demo-state-v1';

function uid(prefix = 'id') {
  return `${prefix}_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
}

function defaultState(): AppState {
  return {
    venue: 'v_hk_001',
    profile: {
      displayName: '你的名字 / 品牌名',
      tagline: '一张名片 · 实时可交互 · 南法奶油风炫彩',
      contact: { email: 'hello@ahelpis.com', wechat: '' },
      status: 'online',
      mission: '你在解决什么？你为什么值得被信任？',
      stack: '你擅长的技术/行业栈（3-7 个关键词）',
      collab: '你希望怎样合作？你能提供什么？你需要什么？',
    },
    greetings: [],
    texts: {},
    help: [],
    posts: [],
    emergencies: [],
  };
}

function normalizeState(raw: unknown): AppState {
  const base = defaultState();
  if (!raw || typeof raw !== 'object') return base;

  const s = raw as Partial<AppState>;
  return {
    ...base,
    ...s,
    profile: { ...base.profile, ...(s.profile ?? {}) },
    greetings: Array.isArray(s.greetings) ? s.greetings : base.greetings,
    texts: s.texts && typeof s.texts === 'object' ? (s.texts as Record<string, TextBlock>) : base.texts,
    help: Array.isArray(s.help) ? s.help : base.help,
    posts: Array.isArray(s.posts) ? s.posts : base.posts,
    emergencies: Array.isArray(s.emergencies) ? s.emergencies : base.emergencies,
  };
}

export function loadState(): AppState {
  const raw = localStorage.getItem(KEY);
  if (raw) {
    try {
      return normalizeState(JSON.parse(raw));
    } catch {
      // fall through to default
    }
  }
  const init = defaultState();
  saveState(init);
  return init;
}

export function saveState(s: AppState) {
  localStorage.setItem(KEY, JSON.stringify(s));
}

export function setVenue(venue: string) {
  const s = loadState();
  s.venue = venue;
  saveState(s);
}

export function updateProfile(patch: Partial<CardProfile>) {
  const s = loadState();
  s.profile = { ...s.profile, ...patch };
  saveState(s);
}

export function addGreeting(input: Omit<Greeting, 'id' | 'createdAt'>) {
  const s = loadState();
  const item: Greeting = { ...input, id: uid('hi'), createdAt: Date.now() };
  s.greetings = [item, ...s.greetings].slice(0, 120);
  saveState(s);
  return item;
}

export function getText(key: string, fallback = '') {
  const s = loadState();
  return s.texts[key]?.text ?? fallback;
}

export function setText(key: string, text: string) {
  const s = loadState();
  s.texts[key] = { key, text, updatedAt: Date.now() };
  saveState(s);
  return s.texts[key];
}

export function addHelp(input: Omit<HelpRequest, 'id' | 'createdAt'>) {
  const s = loadState();
  const item: HelpRequest = { ...input, id: uid('help'), createdAt: Date.now() };
  s.help = [item, ...s.help].slice(0, 200);
  saveState(s);
  return item;
}

export function closeHelp(id: string) {
  const s = loadState();
  s.help = s.help.filter((h) => h.id !== id);
  saveState(s);
}

export function addPost(input: Omit<PublicPost, 'id' | 'createdAt'>) {
  const s = loadState();
  const item: PublicPost = { ...input, id: uid('post'), createdAt: Date.now() };
  s.posts = [item, ...s.posts].slice(0, 400);
  saveState(s);
  return item;
}

export function addEmergency(input: Omit<EmergencyCase, 'id' | 'createdAt'>) {
  const s = loadState();
  const item: EmergencyCase = { ...input, id: uid('ec'), createdAt: Date.now() };
  s.emergencies = [item, ...s.emergencies].slice(0, 200);
  saveState(s);
  return item;
}

export function downloadJson(filename: string, obj: unknown) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

