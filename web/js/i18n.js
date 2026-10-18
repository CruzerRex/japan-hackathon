// UI localisation (English / Japanese). Procedure content itself is never
// machine-translated here: translations are separate, linked, reviewed records.

const D = {
  en: {
    'nav.overview': 'Overview', 'nav.capture': 'Knowledge Capture', 'nav.library': 'Knowledge Library',
    'nav.graph': 'Knowledge Graph', 'nav.academy': 'Training Academy', 'nav.matrix': 'Competency Matrix',
    'nav.risk': 'Knowledge Risk', 'nav.mentorship': 'Mentorship', 'nav.settings': 'Settings',
    'search.placeholder': 'Search procedures, steps, skills, people…', 'assistant.open': 'Ask Kizuna',
    'demo.banner': 'Simulated demo organisation — all people, procedures and records are fictional.',
    'demo.tour': 'Demo tour', 'notifications': 'Review queue', 'signout': 'Sign out', 'switch': 'Switch persona',
    'overview.title': 'Command Center', 'overview.sub': 'Knowledge continuity across your plant, from live application data',
    'capture.title': 'Knowledge Capture Studio', 'capture.sub': 'Record what veteran experts demonstrate, say and know',
    'library.title': 'Knowledge Library', 'library.sub': 'Evidence-linked procedures and their review state',
    'graph.title': 'Knowledge Graph', 'graph.sub': 'How experts, procedures, steps, skills and people connect',
    'academy.title': 'Training Academy', 'academy.sub': 'Expert-approved modules with guided and challenge practice',
    'matrix.title': 'Competency Matrix', 'matrix.sub': 'Validated skills, pending sign-offs and remediation',
    'risk.title': 'Knowledge-Risk Radar', 'risk.sub': 'Where retirement and thin documentation threaten critical skills',
    'mentorship.title': 'Global Mentorship', 'mentorship.sub': 'Connect veterans with younger and international engineers',
    'settings.title': 'Settings', 'settings.sub': 'Organisation, AI providers, scoring rules, access and data portability',
  },
  ja: {
    'nav.overview': '概要', 'nav.capture': 'ナレッジ収集', 'nav.library': 'ナレッジライブラリ', 'nav.graph': 'ナレッジグラフ',
    'nav.academy': 'トレーニング', 'nav.matrix': '力量マトリクス', 'nav.risk': '技能継承リスク', 'nav.mentorship': 'メンター制度',
    'nav.settings': '設定', 'search.placeholder': '手順・ステップ・技能・人を検索…', 'assistant.open': 'Kizunaに質問',
    'demo.banner': 'シミュレーション用デモ組織です。人物・手順・記録はすべて架空のものです。',
    'demo.tour': 'デモツアー', 'notifications': 'レビュー待ち', 'signout': 'サインアウト', 'switch': 'ペルソナ切替',
    'overview.title': 'コマンドセンター', 'overview.sub': '工場全体の技能継承状況(実データに基づく)',
    'capture.title': 'ナレッジ収集スタジオ', 'capture.sub': '熟練者が「見せる・語る・知っている」ことを記録',
    'library.title': 'ナレッジライブラリ', 'library.sub': '根拠に紐づいた手順書とレビュー状況',
    'graph.title': 'ナレッジグラフ', 'graph.sub': '熟練者・手順・工程・技能・人のつながり',
    'academy.title': 'トレーニングアカデミー', 'academy.sub': '熟練者が承認した教材でガイド学習とチャレンジ演習',
    'matrix.title': '力量マトリクス', 'matrix.sub': '認定済み技能・承認待ち・再教育',
    'risk.title': '技能継承リスクレーダー', 'risk.sub': '退職と文書化不足が重要技能を脅かす箇所',
    'mentorship.title': 'グローバル・メンター制度', 'mentorship.sub': '熟練者と若手・外国籍エンジニアをつなぐ',
    'settings.title': '設定', 'settings.sub': '組織・AIプロバイダー・採点ルール・権限・データポータビリティ',
  },
};

let lang = 'en';
try { lang = localStorage.getItem('kf.lang') || 'en'; } catch { /* storage unavailable */ }

export function getLang() { return lang; }
export function setLang(l) {
  lang = D[l] ? l : 'en';
  document.documentElement.lang = lang;
  try { localStorage.setItem('kf.lang', lang); } catch { /* ignore */ }
}
export function t(key) { return (D[lang] && D[lang][key]) || D.en[key] || key; }
/** Pick the Japanese variant of a name when the UI is in Japanese. */
export function nm(en, ja) { return lang === 'ja' && ja ? ja : en; }
document.documentElement.lang = lang;
