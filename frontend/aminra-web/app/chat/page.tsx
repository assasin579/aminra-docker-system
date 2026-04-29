'use client';
// Chat page for Halal certification AI assistant
import { useState, useRef, useEffect } from 'react';
import { useTranslation } from 'react-i18next';

type Message = {
  id: number;
  text: string;
  sender: 'user' | 'assistant';
  timestamp: Date;
};

export default function HomePage() {
  const { t, i18n } = useTranslation();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);

  useEffect(() => {
    setMessages((prev) => {
      const rest = prev.filter((m) => m.id !== 1);
      return [
        { id: 1, text: t('home.initial_message'), sender: 'assistant', timestamp: new Date() },
        ...rest,
      ];
    });
  }, [i18n.language]);

  const [loading, setLoading] = useState(false);
  const [streamingId, setStreamingId] = useState<number | null>(null);
  const [isListening, setIsListening] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(false);
  const [speakingId, setSpeakingId] = useState<number | null>(null);
  const [availableVoices, setAvailableVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [selectedVoiceName, setSelectedVoiceName] = useState<string>('');
  const [showVoicePicker, setShowVoicePicker] = useState(false);
  const recognitionRef = useRef<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const [showScrollDown, setShowScrollDown] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const langMap: Record<string, string> = {
    vi: 'vi-VN', en: 'en-US', ms: 'ms-MY', ar: 'ar-SA',
  };

  // STT setup
  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (SpeechRecognition) {
      setVoiceSupported(true);
      const recognition = new SpeechRecognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.onresult = (event: any) => {
        let interim = '';
        let final = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const t = event.results[i][0].transcript;
          if (event.results[i].isFinal) final += t;
          else interim += t;
        }
        setInput(final || interim);
      };
      recognition.onend = () => setIsListening(false);
      recognition.onerror = () => setIsListening(false);
      recognitionRef.current = recognition;
    }
  }, []);

  // Update STT lang + cancel TTS on language switch
  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.lang = langMap[i18n.language] || 'vi-VN';
    }
    window.speechSynthesis?.cancel();
    setSpeakingId(null);
  }, [i18n.language]);

  const toggleListening = () => {
    if (!recognitionRef.current) return;
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      setInput('');
      recognitionRef.current.start();
      setIsListening(true);
    }
  };

  // TTS voices
  const loadVoices = () => {
    const lang = langMap[i18n.language] || 'vi-VN';
    const all = window.speechSynthesis.getVoices();
    const matched = all
      .filter(v => v.lang.startsWith(lang.split('-')[0]))
      .sort((a, b) => {
        if (!a.localService && b.localService) return -1;
        if (a.localService && !b.localService) return 1;
        return 0;
      });
    setAvailableVoices(matched);
    if (matched.length > 0) {
      setSelectedVoiceName(prev => matched.find(v => v.name === prev) ? prev : matched[0].name);
    }
  };

  useEffect(() => {
    if (!window.speechSynthesis) return;
    loadVoices();
    window.speechSynthesis.onvoiceschanged = loadVoices;
  }, [i18n.language]);

  const speakMessage = (msg: Message) => {
    if (!window.speechSynthesis) return;
    if (speakingId === msg.id) {
      window.speechSynthesis.cancel();
      setSpeakingId(null);
      return;
    }
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(msg.text);
    utter.lang = langMap[i18n.language] || 'vi-VN';
    utter.rate = 0.95;
    utter.pitch = 1.0;
    const voice = availableVoices.find(v => v.name === selectedVoiceName);
    if (voice) utter.voice = voice;
    utter.onend = () => setSpeakingId(null);
    utter.onerror = () => setSpeakingId(null);
    setSpeakingId(msg.id);
    window.speechSynthesis.speak(utter);
  };

  const isNearBottom = () => {
    const c = messagesContainerRef.current;
    if (!c) return true;
    return c.scrollHeight - c.scrollTop - c.clientHeight < 120;
  };

  const scrollToBottom = (force = false) => {
    const c = messagesContainerRef.current;
    if (!c) return;
    if (force || isNearBottom()) {
      c.scrollTop = c.scrollHeight;
    }
  };

  // Khi gửi tin nhắn mới: force scroll xuống đáy (bỏ qua tin chào mừng ban đầu)
  useEffect(() => {
    if (messages.length > 1) scrollToBottom(true);
  }, [messages.length]);

  // Khi đang stream: scroll nhẹ nếu user đang ở gần đáy
  useEffect(() => {
    if (streamingId) scrollToBottom(false);
  }, [messages]);

  // Hiện nút scroll-to-top / scroll-to-bottom (cả container lẫn window cho mobile)
  useEffect(() => {
    const onScroll = () => {
      const c = messagesContainerRef.current;
      const containerTop = c ? c.scrollTop > 300 : false;
      const windowTop = window.scrollY > 300;
      setShowScrollTop(containerTop || windowTop);

      const containerBottom = c ? (c.scrollHeight - c.scrollTop - c.clientHeight > 120) : false;
      const windowBottom = window.scrollY + window.innerHeight < document.body.scrollHeight - 120;
      setShowScrollDown(containerBottom || windowBottom);
    };
    const c = messagesContainerRef.current;
    if (c) c.addEventListener('scroll', onScroll);
    window.addEventListener('scroll', onScroll);
    return () => {
      if (c) c.removeEventListener('scroll', onScroll);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  const handleSend = async () => {
    if (!input.trim()) return;

    // Ẩn bàn phím mobile trước khi xử lý
    (document.activeElement as HTMLElement)?.blur();

    if (isListening && recognitionRef.current) {
      recognitionRef.current.stop();
      setIsListening(false);
    }

    const now = Date.now();
    const userMessage: Message = {
      id: now,
      text: input,
      sender: 'user',
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    const assistantId = now + 1;

    try {
      const apiUrl = `/api/chat/stream`;
      // Build history từ các tin nhắn trước (bỏ tin nhắn chào mặc định id=1, giới hạn 6 messages gần nhất)
      const history = messages
        .filter((m) => m.id !== 1)
        .slice(-6)
        .map((m) => ({ role: m.sender === 'user' ? 'user' : 'assistant', content: m.text }));
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: input, lang: i18n.language, history }),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      setMessages((prev) => [...prev, { id: assistantId, text: '', sender: 'assistant', timestamp: new Date() }]);
      setLoading(false);
      setStreamingId(assistantId);

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      const IDLE_TIMEOUT_MS = 25000;
      let idleTimer: ReturnType<typeof setTimeout> | null = null;
      const resetIdle = () => {
        if (idleTimer) clearTimeout(idleTimer);
        idleTimer = setTimeout(() => { reader.cancel(); }, IDLE_TIMEOUT_MS);
      };
      resetIdle();
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          resetIdle();
          const chunk = decoder.decode(value, { stream: true });
          setMessages((prev) =>
            prev.map((m) => m.id === assistantId ? { ...m, text: m.text + chunk } : m)
          );
        }
      } finally {
        if (idleTimer) clearTimeout(idleTimer);
      }
    } catch (error) {
      setMessages((prev) => {
        const hasMsg = prev.some((m) => m.id === assistantId);
        const errMsg = { id: assistantId, text: 'Error: Unable to get response from AI. Please try again.', sender: 'assistant' as const, timestamp: new Date() };
        return hasMsg ? prev.map((m) => m.id === assistantId ? errMsg : m) : [...prev, errMsg];
      });
    } finally {
      setLoading(false);
      setStreamingId(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const whyItems = [
    {
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
      titleKey: 'home.why1_title', descKey: 'home.why1_desc', color: '#0A1F44', bg: 'rgba(10,31,68,0.12)'
    },
    {
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
      ),
      titleKey: 'home.why2_title', descKey: 'home.why2_desc', color: '#6B7280', bg: 'rgba(91,107,125,0.12)'
    },
    {
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      ),
      titleKey: 'home.why3_title', descKey: 'home.why3_desc', color: '#f59e0b', bg: 'rgba(245,158,11,0.15)'
    },
    {
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064" />
        </svg>
      ),
      titleKey: 'home.why4_title', descKey: 'home.why4_desc', color: '#8b5cf6', bg: 'rgba(139,92,246,0.15)'
    },
    {
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      titleKey: 'home.why5_title', descKey: 'home.why5_desc', color: '#102A5C', bg: 'rgba(16,185,129,0.15)'
    },
    {
      icon: (
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      titleKey: 'home.why6_title', descKey: 'home.why6_desc', color: '#06b6d4', bg: 'rgba(6,182,212,0.15)'
    },
  ];

  return (
    <div className="flex flex-col flex-1 lg:min-h-0 w-full" data-page>
      {/* 2-column layout */}
      <div className="flex flex-col lg:flex-row gap-4 flex-1 lg:min-h-0">

      {/* Chat Container */}
      <div className="flex-1 lg:min-h-0 rounded-2xl shadow-xl overflow-hidden flex flex-col" style={{background:'#FFFFFF', border:'1px solid #E2E8F0'}}>
        {/* Chat Header */}
        <div className="p-4" style={{borderBottom:'1px solid #E2E8F0', background:'#FFFFFF'}}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative flex-shrink-0">
                <div className="h-11 w-11 rounded-full overflow-hidden ring-2 ring-[#0A1F44]/50" style={{animation:'pulse-ring 2.5s ease-in-out infinite'}}>
                  <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" className="w-full h-full">
                    {/* App bg fill */}
                    <circle cx="50" cy="50" r="50" fill="#F5F1E8"/>
                    {/* Blue coat - bottom 35% */}
                    <ellipse cx="50" cy="97" rx="40" ry="22" fill="#4070b8"/>
                    {/* Pink hijab scarf draping over coat */}
                    <path d="M26 60 Q18 78 20 100 L50 90 L80 100 Q82 78 74 60 Q63 70 50 70 Q37 70 26 60Z" fill="#c8607a"/>
                    {/* Pink hijab circle - head */}
                    <circle cx="50" cy="36" r="34" fill="#c8607a"/>
                    {/* White forehead band */}
                    <path d="M27 19 Q50 9 73 19 Q73 27 50 29 Q27 27 27 19Z" fill="white"/>
                    {/* Face */}
                    <ellipse cx="50" cy="41" rx="20" ry="24" fill="#f5dcc8"/>
                    {/* Eyebrows */}
                    <path d="M33 31 Q40 26.5 47 31" stroke="#2d2d2d" strokeWidth="3" fill="none" strokeLinecap="round"/>
                    <path d="M53 31 Q60 26.5 67 31" stroke="#2d2d2d" strokeWidth="3" fill="none" strokeLinecap="round"/>
                    {/* Eyes */}
                    <circle cx="41" cy="38" r="5" fill="#1a1a1a"/>
                    <circle cx="59" cy="38" r="5" fill="#1a1a1a"/>
                    <circle cx="43" cy="36" r="1.6" fill="white"/>
                    <circle cx="61" cy="36" r="1.6" fill="white"/>
                    {/* Nose */}
                    <ellipse cx="50" cy="47" rx="3" ry="2.2" fill="#dda080" opacity="0.75"/>
                    {/* Mouth - red open smile */}
                    <path d="M38 54 Q50 65 62 54 Q50 58 38 54Z" fill="#c0392b"/>
                    <path d="M39 54.5 Q50 60 61 54.5 Q50 56.5 39 54.5Z" fill="white"/>
                    {/* Buttons on coat */}
                    <circle cx="50" cy="82" r="2.5" fill="white"/>
                    <circle cx="50" cy="89" r="2.5" fill="white"/>
                    <circle cx="50" cy="96" r="2.5" fill="white"/>
                  </svg>
                </div>
                <div className="absolute bottom-0 right-0 h-3 w-3 rounded-full bg-[#0A1F44]" style={{outline:'2px solid #FFFFFF', animation:'blink 1.8s ease-in-out infinite'}}></div>
              </div>
              <div>
                <h2 className="text-base font-semibold leading-tight" style={{color:'#0A1F44'}}>{t('home.chat_title')}</h2>
                <p className="text-xs flex items-center gap-1" style={{color:'#0A1F44'}}>
                  <span className="inline-block h-1.5 w-1.5 rounded-full" style={{background:'#0A1F44', animation:'blink 1.8s ease-in-out infinite'}}></span>
                  {t('home.online')}
                </p>
              </div>
            </div>
            {/* Voice picker */}
            {availableVoices.length > 1 && (
              <div className="relative">
                <button
                  onClick={() => setShowVoicePicker(p => !p)}
                  title="Chọn giọng đọc"
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors"
                  style={{border:'1px solid #E2E8F0', background:'#FFFFFF', color:'#6B7280'}}
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.536 8.464a5 5 0 010 7.072M18.364 5.636a9 9 0 010 12.728M12 6v12m0 0l-3-3m3 3l3-3"/>
                  </svg>
                  <span className="max-w-[80px] truncate">{selectedVoiceName.split(' ')[0]}</span>
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"/>
                  </svg>
                </button>
                {showVoicePicker && (
                  <div className="absolute right-0 top-full mt-1 z-50 rounded-xl shadow-xl overflow-hidden min-w-[220px]"
                    style={{background:'#FFFFFF', border:'1px solid #E2E8F0'}}>
                    <div className="px-3 py-2 text-xs" style={{color:'#6B7280', borderBottom:'1px solid #E2E8F0'}}>
                      Chọn giọng đọc ({availableVoices.length} giọng)
                    </div>
                    {availableVoices.map(v => (
                      <button key={v.name} onClick={() => { setSelectedVoiceName(v.name); setShowVoicePicker(false); }}
                        className="w-full text-left px-3 py-2.5 text-sm transition-colors flex items-center justify-between gap-2"
                        style={{ color: selectedVoiceName === v.name ? '#0A1F44' : '#374151', background: selectedVoiceName === v.name ? 'rgba(10,31,68,0.06)' : 'transparent' }}>
                        <span className="truncate">{v.name}</span>
                        {!v.localService && <span className="text-xs flex-shrink-0" style={{color:'#0A1F44'}}>online</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <style>{`
          @keyframes pulse-ring {
            0%, 100% { box-shadow: 0 0 0 0 rgba(10,31,68,0.4); }
            50% { box-shadow: 0 0 0 6px rgba(10,31,68,0); }
          }
          @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
          }
          @keyframes soundwave {
            0%, 100% { transform: scaleY(1); opacity: 0.6; }
            50% { transform: scaleY(2); opacity: 1; }
          }
        `}</style>

        {/* Messages Area */}
        <div className="relative flex-1 lg:min-h-0 min-h-[300px] flex flex-col" style={{background:'#FFFFFF'}}>
        {showScrollTop && (
          <button
            onClick={() => {
              messagesContainerRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }}
            className="fixed bottom-36 right-4 z-50 p-2.5 rounded-full shadow-lg transition-all hover:scale-110 lg:absolute lg:bottom-auto lg:top-3 lg:right-3"
            style={{background:'#FFFFFF', border:'1px solid #E2E8F0'}}
            title="Lên đầu trang"
          >
            <svg className="w-4 h-4" style={{color:'#0A1F44'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 15l7-7 7 7"/>
            </svg>
          </button>
        )}
        {showScrollDown && (
          <button
            onClick={() => {
              const c = messagesContainerRef.current;
              if (c) c.scrollTo({ top: c.scrollHeight, behavior: 'smooth' });
              inputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
              setTimeout(() => inputRef.current?.focus(), 400);
            }}
            className="fixed bottom-24 right-4 z-50 p-2.5 rounded-full shadow-lg transition-all hover:scale-110 lg:absolute lg:bottom-auto lg:top-12 lg:right-3"
            style={{background:'#FFFFFF', border:'1px solid #E2E8F0'}}
            title="Xuống cuối trang"
          >
            <svg className="w-4 h-4" style={{color:'#0A1F44'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7"/>
            </svg>
          </button>
        )}
        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <div key={msg.id} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[80%] rounded-2xl p-4 shadow-sm`}
                style={msg.sender === 'user'
                  ? {background:'#0A1F44', color:'white'}
                  : {background: speakingId === msg.id ? '#DCE3F0' : '#F5F1E8', border:`1px solid ${speakingId === msg.id ? '#0A1F44' : '#E2E8F0'}`, color:'#0A1F44'}}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium">
                    {msg.sender === 'user' ? t('chat.user') : t('chat.assistant')}
                  </div>
                  <div className="flex items-center gap-2">
                    {msg.sender === 'assistant' && (
                      <button
                        onClick={() => speakMessage(msg)}
                        title={speakingId === msg.id ? 'Dừng đọc' : 'Nghe câu trả lời'}
                        aria-label={speakingId === msg.id ? 'Dừng đọc' : 'Nghe câu trả lời'}
                        className="opacity-60 hover:opacity-100 transition-opacity p-2 -m-2 rounded touch-manipulation"
                      >
                        {speakingId === msg.id ? (
                          <svg className="w-4 h-4" style={{color:'#0A1F44'}} fill="currentColor" viewBox="0 0 24 24">
                            <rect x="6" y="6" width="4" height="12" rx="1"/>
                            <rect x="14" y="6" width="4" height="12" rx="1"/>
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" style={{color:'#6B7280'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.536 8.464a5 5 0 010 7.072M12 6v12m0 0l-3-3m3 3l3-3M9.172 9.172a4 4 0 000 5.656"/>
                          </svg>
                        )}
                      </button>
                    )}
                    <div className="text-xs opacity-70" suppressHydrationWarning>
                      {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                </div>
                <div className="whitespace-pre-wrap">
                  {msg.text}
                  {streamingId === msg.id && (
                    <span className="inline-block w-0.5 h-4 ml-0.5 align-middle" style={{background:'#0A1F44', animation:'blink 0.8s ease-in-out infinite'}} />
                  )}
                </div>
                {speakingId === msg.id && (
                  <div className="flex items-center gap-1 mt-2">
                    {[0, 0.15, 0.3, 0.15, 0].map((delay, i) => (
                      <span key={i} className="inline-block w-0.5 rounded-full"
                        style={{background:'#0A1F44', height:`${8 + i * 3}px`, animation:'soundwave 0.8s ease-in-out infinite', animationDelay:`${delay}s`}}
                      />
                    ))}
                    <span className="text-xs ml-1" style={{color:'#0A1F44'}}>Đang đọc...</span>
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl p-4" style={{background:'#F5F1E8', border:'1px solid #E2E8F0'}}>
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{background:'#0A1F44'}}></div>
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{background:'#0A1F44', animationDelay: '0.2s'}}></div>
                  <div className="w-2 h-2 rounded-full animate-bounce" style={{background:'#0A1F44', animationDelay: '0.4s'}}></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-6" style={{borderTop:'1px solid #E2E8F0', background:'#FFFFFF'}}>
          <div className="flex items-end gap-3">
            <div className="flex-1 relative">
              <textarea
                ref={inputRef}
                className="w-full rounded-xl p-4 focus:ring-2 focus:ring-[#0A1F44] focus:outline-none resize-none"
                style={{background:'#FFFFFF', border:`1px solid ${isListening ? '#0A1F44' : '#E2E8F0'}`, color:'#0A1F44'}}
                placeholder={isListening ? t('home.listening') : t('home.input_placeholder')}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={2}
              />
              {isListening && (
                <div className="absolute bottom-3 right-3 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" style={{animation:'blink 0.8s ease-in-out infinite'}}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" style={{animation:'blink 0.8s ease-in-out infinite', animationDelay:'0.2s'}}></span>
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" style={{animation:'blink 0.8s ease-in-out infinite', animationDelay:'0.4s'}}></span>
                </div>
              )}
            </div>
            <div className="flex flex-col gap-2">
              {voiceSupported && (
                <button
                  onClick={toggleListening}
                  disabled={loading}
                  title={isListening ? 'Dừng ghi âm' : 'Nhận diện giọng nói'}
                  className={`p-3 rounded-xl transition-all ${isListening ? 'bg-red-500 hover:bg-red-400 shadow-lg shadow-red-500/30' : 'hover:bg-[#0A1F44]/10'}`}
                  style={isListening ? {} : {border:'1px solid #E2E8F0', background:'#FFFFFF'}}
                >
                  {isListening ? (
                    <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
                      <rect x="6" y="6" width="12" height="12" rx="2"/>
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" style={{color:'#0A1F44'}} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/>
                    </svg>
                  )}
                </button>
              )}
              <button
                onClick={handleSend}
                disabled={loading || !input.trim()}
                className="px-8 py-4 text-white font-semibold rounded-xl disabled:opacity-50 transition-all shadow-md"
                style={{background:'#0A1F44'}}
              >
                {loading ? t('home.thinking') : t('home.send')}
              </button>
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {(['preset1', 'preset2', 'preset3', 'preset4'] as const).map((key) => (
              <button
                key={key}
                onClick={() => setInput(t(`home.${key}`))}
                disabled={loading}
                className="px-3 py-1.5 rounded-full text-xs font-medium transition-all hover:scale-105 disabled:opacity-40"
                style={{background:'#F5F1E8', border:'1px solid #E2E8F0', color:'#374151'}}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = '#0A1F44'; (e.currentTarget as HTMLElement).style.color = '#0A1F44'; }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = '#E2E8F0'; (e.currentTarget as HTMLElement).style.color = '#374151'; }}
              >
                {t(`home.${key}`)}
              </button>
            ))}
          </div>
          <div className="mt-2 text-xs" style={{color:'#94A3B8'}}>
            {t('home.enter_hint')}
          </div>
        </div>
      </div>
      </div>

      {/* Why Choose Aminra */}
      <div className="lg:w-80 rounded-2xl overflow-hidden flex flex-col lg:min-h-0" style={{background:'#FFFFFF', border:'1px solid #E2E8F0'}}>
        <div className="px-5 pt-5 pb-3">
          <h3 className="text-lg font-bold" style={{color:'#0A1F44'}}>{t('home.why_title')}</h3>
          <div className="h-0.5 mt-3 rounded-full" style={{background:'linear-gradient(to right, #0A1F44, transparent)'}}></div>
        </div>
        <div className="px-3 pb-4 space-y-1 overflow-y-auto flex-1 lg:min-h-0">
          {whyItems.map((item) => (
            <div
              key={item.titleKey}
              className="flex items-start gap-3 px-3 py-3 rounded-xl cursor-default transition-all duration-200 group"
              onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = '#F5F1E8'}
              onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
            >
              <div
                className="h-8 w-8 rounded-lg flex items-center justify-center flex-shrink-0 transition-transform duration-200 group-hover:scale-110"
                style={{background: item.bg, color: item.color}}
              >
                {item.icon}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold leading-tight" style={{color:'#0A1F44'}}>{t(item.titleKey)}</div>
                <div className="text-xs mt-0.5 leading-relaxed" style={{color:'#6B7280'}}>{t(item.descKey)}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      </div>
    </div>
  );
}
