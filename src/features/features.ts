export type Phase = 'past' | 'now' | 'future';

export type FeatureItem = {
  id: string;
  phase: Phase;
  title: string;
  subtitle: string;
  href: string;
};

// 说明：
// - pass：个人叙事与可信度（你是谁、怎么走到现在）
// - now：用户可立即使用的核心功能（名片/互助/公共消息/机器人4S）
// - future：高风险/高价值能力与升级通道（紧急事件→官方包、Universe 选项等）
export const FEATURES: FeatureItem[] = [
  // pass
  { id: 'origin', phase: 'past', title: 'origin', subtitle: '为什么走到今天', href: '/past/origin' },
  { id: 'turning-point', phase: 'past', title: 'turning point', subtitle: '关键选择与作品', href: '/past/turning-point' },
  { id: 'craft', phase: 'past', title: 'craft', subtitle: '方法论与取舍', href: '/past/craft' },

  // now
  { id: 'card', phase: 'now', title: 'card', subtitle: '名片交友 / 打招呼', href: '/now/card' },
  { id: 'help', phase: 'now', title: 'help', subtitle: '实时获得帮助（Now）', href: '/now/help' },
  { id: 'public', phase: 'now', title: 'public', subtitle: '公共消息（Keep）', href: '/now/public' },
  { id: 'robot4s', phase: 'now', title: 'robot 4S', subtitle: '机器人相关服务与交易', href: '/now/robot4s' },

  // future
  { id: 'emergency', phase: 'future', title: 'emergency', subtitle: '按理由归类 → 导出官方包', href: '/future/emergency' },
  { id: 'universe', phase: 'future', title: 'universe', subtitle: '扩展选项（可嵌入外部能力）', href: '/future/universe' },
];

export const PHASE_LABEL: Record<Phase, string> = {
  past: 'pass',
  now: 'now',
  future: 'future',
};

