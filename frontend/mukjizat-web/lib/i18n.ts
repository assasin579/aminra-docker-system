import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

const resources = {
  en: {
    common: {
      navbar: {
        home: "Chat with Mukjizat Saigoncert",
        upload: "Document Review",
        language: "Language",
        switch: "Switch language"
      },
      home: {
        title: "Mukjizat Saigoncert Assistant",
        title_prefix: "AI-Powered ",
        title_highlight: "Halal Certification",
        title_suffix: " Assistant",
        subtitle: "Ask questions about Halal certification",
        chat_title: "Halal Q&A",
        chat_subtitle: "Powered by LLM & Qdrant vector database",
        online: "Online",
        enter_hint: "Press Enter to send, Shift+Enter for new line",
        initial_message: "Hello! I am Mukjizat Saigoncert. Ask me anything about Halal certification.",
        why_title: "Why Choose Mukjizat Saigoncert?",
        why1_title: "Document-Based",
        why1_desc: "Answers sourced from official HDC, JAKIM, and MUI documents",
        why2_title: "Smart Retrieval",
        why2_desc: "Finds relevant information across thousands of pages",
        why3_title: "Fast Responses",
        why3_desc: "Get answers in seconds, not hours of research",
        why4_title: "Multi-Language",
        why4_desc: "Supports English, Arabic, and Vietnamese",
        why5_title: "Verified Sources",
        why5_desc: "Every answer references official Halal standards",
        why6_title: "24/7 Availability",
        why6_desc: "Available anytime, anywhere",
        input_placeholder: "Type your question here...",
        send: "Send",
        thinking: "Thinking...",
        error: "Error occurred. Please try again.",
        preset1: "Halal Certification Process",
        preset2: "Halal Market News",
        preset3: "Business Opportunities",
        preset4: "Halal Certification Bodies in Vietnam",
        listening: "🎙️ Listening..."
      },
      upload: {
        title: "Upload Documents",
        subtitle: "Upload PDF, DOCX files for analysis",
        drag_drop: "Drag & drop files here, or click to select",
        drag_active: "Drop file here",
        file_types: "PDF, DOC, DOCX, TXT, MD — max 50MB",
        supported_formats: "Supported formats",
        browse: "Browse files",
        uploading: "Uploading...",
        success: "Upload successful! Analysis results will appear here.",
        error: "Upload failed. Please try again.",
        how_it_works: "How it works",
        step1_title: "Upload document",
        step1_desc: "Halal certification, ingredient lists, supplier documents",
        step2_title: "AI analysis",
        step2_desc: "LLM scans content and compares with Halal standards database",
        step3_title: "Get suggestions",
        step3_desc: "Receive compliance feedback and improvement tips",
        uploaded_files: "Uploaded Files",
        track_progress: "Track progress and view results",
        no_files: "No files uploaded yet",
        no_files_hint: "Upload documents to see results"
      },
      chat: {
        user: "You",
        assistant: "Mukjizat Saigoncert"
      }
    }
  },
  vi: {
    common: {
      navbar: {
        home: "Chat với Mukjizat Saigoncert",
        upload: "Đánh giá tài liệu",
        language: "Ngôn ngữ",
        switch: "Chuyển ngôn ngữ"
      },
      home: {
        title: "Trợ lý AI Mukjizat Saigoncert",
        title_prefix: "Trợ lý AI ",
        title_highlight: "Chứng nhận Halal",
        title_suffix: " Thông minh",
        subtitle: "Đặt câu hỏi về chứng nhận Halal",
        chat_title: "Hỏi đáp về Halal",
        chat_subtitle: "Được hỗ trợ bởi LLM & cơ sở dữ liệu Qdrant",
        online: "Trực tuyến",
        enter_hint: "Nhấn Enter để gửi, Shift+Enter để xuống dòng",
        initial_message: "Xin chào! Tôi là Mukjizat Saigoncert. Hãy hỏi tôi bất cứ điều gì về chứng nhận Halal.",
        why_title: "Tại sao chọn Mukjizat Saigoncert?",
        why1_title: "Dựa trên tài liệu",
        why1_desc: "Câu trả lời từ tài liệu chính thức HDC, JAKIM và MUI",
        why2_title: "Truy xuất thông minh",
        why2_desc: "Tìm kiếm thông tin liên quan trong hàng nghìn trang",
        why3_title: "Phản hồi nhanh",
        why3_desc: "Nhận câu trả lời trong vài giây",
        why4_title: "Đa ngôn ngữ",
        why4_desc: "Hỗ trợ tiếng Anh, tiếng Ả Rập và tiếng Việt",
        why5_title: "Nguồn đã kiểm chứng",
        why5_desc: "Mọi câu trả lời đều tham chiếu tiêu chuẩn Halal chính thức",
        why6_title: "Luôn sẵn sàng 24/7",
        why6_desc: "Truy cập mọi lúc, mọi nơi",
        input_placeholder: "Nhập câu hỏi của bạn...",
        send: "Gửi",
        thinking: "Đang suy nghĩ...",
        error: "Đã xảy ra lỗi. Vui lòng thử lại.",
        preset1: "Quy trình chứng nhận Halal",
        preset2: "Tin tức về thị trường Halal",
        preset3: "Cơ hội kinh doanh",
        preset4: "Các tổ chức chứng nhận Halal ở Việt Nam",
        listening: "🎙️ Đang lắng nghe..."
      },
      upload: {
        title: "Tải lên Tài liệu",
        subtitle: "Tải lên file PDF, DOCX để phân tích",
        drag_drop: "Kéo & thả file vào đây, hoặc click để chọn",
        drag_active: "Thả file vào đây",
        file_types: "PDF, DOC, DOCX, TXT, MD — tối đa 50MB",
        supported_formats: "Định dạng hỗ trợ",
        browse: "Chọn file",
        uploading: "Đang tải lên...",
        success: "Tải lên thành công! Kết quả phân tích sẽ hiển thị ở đây.",
        error: "Tải lên thất bại. Vui lòng thử lại.",
        how_it_works: "Cách hoạt động",
        step1_title: "Tải lên tài liệu",
        step1_desc: "Chứng nhận Halal, danh sách thành phần, tài liệu nhà cung cấp",
        step2_title: "Phân tích AI",
        step2_desc: "LLM quét nội dung và so sánh với cơ sở dữ liệu tiêu chuẩn Halal",
        step3_title: "Nhận gợi ý",
        step3_desc: "Nhận phản hồi tuân thủ và các mẹo cải thiện",
        uploaded_files: "Tệp đã tải lên",
        track_progress: "Theo dõi tiến độ và xem kết quả",
        no_files: "Chưa có tệp nào được tải lên",
        no_files_hint: "Tải lên tài liệu để xem kết quả"
      },
      chat: {
        user: "Bạn",
        assistant: "Mukjizat Saigoncert"
      }
    }
  },
  ms: {
    common: {
      navbar: {
        home: "Chat dengan Mukjizat Saigoncert",
        upload: "Semakan Dokumen",
        language: "Bahasa",
        switch: "Tukar bahasa"
      },
      home: {
        title: "Pembantu AI Mukjizat Saigoncert",
        title_prefix: "Pembantu AI ",
        title_highlight: "Pensijilan Halal",
        title_suffix: " Pintar",
        subtitle: "Tanya soalan tentang pensijilan Halal",
        chat_title: "Soal Jawab Halal",
        chat_subtitle: "Dikuasakan oleh LLM & pangkalan data Qdrant",
        online: "Dalam Talian",
        enter_hint: "Tekan Enter untuk hantar, Shift+Enter untuk baris baru",
        initial_message: "Helo! Saya Mukjizat Saigoncert. Tanya saya apa sahaja tentang pensijilan Halal.",
        why_title: "Mengapa Pilih Mukjizat Saigoncert?",
        why1_title: "Berasaskan Dokumen",
        why1_desc: "Jawapan bersumber daripada dokumen rasmi HDC, JAKIM dan MUI",
        why2_title: "Carian Pintar",
        why2_desc: "Mencari maklumat berkaitan dalam ribuan halaman",
        why3_title: "Respons Pantas",
        why3_desc: "Dapatkan jawapan dalam beberapa saat",
        why4_title: "Pelbagai Bahasa",
        why4_desc: "Menyokong Bahasa Inggeris, Arab dan Vietnam",
        why5_title: "Sumber Disahkan",
        why5_desc: "Setiap jawapan merujuk piawaian Halal rasmi",
        why6_title: "Sedia 24/7",
        why6_desc: "Boleh diakses bila-bila masa, di mana-mana",
        input_placeholder: "Taip soalan anda di sini...",
        send: "Hantar",
        thinking: "Sedang berfikir...",
        error: "Ralat berlaku. Sila cuba lagi.",
        preset1: "Proses Pensijilan Halal",
        preset2: "Berita Pasaran Halal",
        preset3: "Peluang Perniagaan",
        preset4: "Badan Pensijilan Halal di Vietnam",
        listening: "🎙️ Sedang mendengar..."
      },
      upload: {
        title: "Muat Naik Dokumen",
        subtitle: "Muat naik fail PDF, DOCX untuk analisis",
        drag_drop: "Seret & lepas fail di sini, atau klik untuk pilih",
        drag_active: "Lepaskan fail di sini",
        file_types: "PDF, DOC, DOCX, TXT, MD — maks 50MB",
        supported_formats: "Format yang disokong",
        browse: "Semak fail",
        uploading: "Sedang memuat naik...",
        success: "Muat naik berjaya! Keputusan analisis akan dipaparkan di sini.",
        error: "Muat naik gagal. Sila cuba lagi.",
        how_it_works: "Cara ia berfungsi",
        step1_title: "Muat naik dokumen",
        step1_desc: "Pensijilan Halal, senarai bahan, dokumen pembekal",
        step2_title: "Analisis AI",
        step2_desc: "LLM mengimbas kandungan dan membandingkan dengan pangkalan data piawaian Halal",
        step3_title: "Dapatkan cadangan",
        step3_desc: "Terima maklum balas pematuhan dan tips penambahbaikan",
        uploaded_files: "Fail Dimuat Naik",
        track_progress: "Jejak kemajuan dan lihat keputusan",
        no_files: "Tiada fail dimuat naik lagi",
        no_files_hint: "Muat naik dokumen untuk lihat keputusan"
      },
      chat: {
        user: "Anda",
        assistant: "Mukjizat Saigoncert"
      }
    }
  },
  ar: {
    common: {
      navbar: {
        home: "محادثة مع أميرة",
        upload: "مراجعة المستندات",
        language: "اللغة",
        switch: "تبديل اللغة"
      },
      home: {
        title: "مساعد أميرة",
        title_prefix: "مساعد الذكاء الاصطناعي ",
        title_highlight: "شهادة الحلال",
        title_suffix: "",
        subtitle: "اطرح أسئلة حول شهادة الحلال",
        chat_title: "أسئلة وأجوبة حول الحلال",
        chat_subtitle: "مدعوم بـ LLM وقاعدة بيانات Qdrant",
        online: "متصل",
        enter_hint: "اضغط Enter للإرسال، Shift+Enter لسطر جديد",
        initial_message: "مرحباً! أنا أميرة. اسألني أي شيء عن شهادة الحلال.",
        why_title: "لماذا تختار أميرة؟",
        why1_title: "مبني على المستندات",
        why1_desc: "إجابات من وثائق HDC وJAKIM وMUI الرسمية",
        why2_title: "استرجاع ذكي",
        why2_desc: "يجد المعلومات ذات الصلة في آلاف الصفحات",
        why3_title: "ردود سريعة",
        why3_desc: "احصل على إجابات في ثوانٍ",
        why4_title: "متعدد اللغات",
        why4_desc: "يدعم الإنجليزية والعربية والفيتنامية",
        why5_title: "مصادر موثقة",
        why5_desc: "كل إجابة تستند إلى معايير الحلال الرسمية",
        why6_title: "متاح 24/7",
        why6_desc: "في أي وقت ومن أي مكان",
        input_placeholder: "اكتب سؤالك هنا...",
        send: "إرسال",
        thinking: "جاري التفكير...",
        error: "حدث خطأ. يرجى المحاولة مرة أخرى.",
        preset1: "عملية شهادة الحلال",
        preset2: "أخبار سوق الحلال",
        preset3: "فرص الأعمال",
        preset4: "هيئات إصدار شهادات الحلال في فيتنام",
        listening: "🎙️ جاري الاستماع..."
      },
      upload: {
        title: "رفع المستندات",
        subtitle: "رفع ملفات PDF، DOCX للتحليل",
        drag_drop: "اسحب وأفلت الملفات هنا، أو انقر للاختيار",
        drag_active: "أفلت الملف هنا",
        file_types: "PDF، DOC، DOCX، TXT، MD — الحد الأقصى 50MB",
        supported_formats: "الصيغ المدعومة",
        browse: "استعرض الملفات",
        uploading: "جاري الرفع...",
        success: "تم الرفع بنجاح! ستظهر نتائج التحليل هنا.",
        error: "فشل الرفع. يرجى المحاولة مرة أخرى.",
        how_it_works: "كيف يعمل",
        step1_title: "رفع المستند",
        step1_desc: "شهادات الحلال، قوائم المكونات، وثائق الموردين",
        step2_title: "تحليل الذكاء الاصطناعي",
        step2_desc: "يفحص LLM المحتوى ويقارنه بقاعدة بيانات معايير الحلال",
        step3_title: "الحصول على اقتراحات",
        step3_desc: "احصل على تغذية راجعة حول الامتثال ونصائح التحسين",
        uploaded_files: "الملفات المرفوعة",
        track_progress: "تتبع التقدم وعرض النتائج",
        no_files: "لم يتم رفع أي ملفات بعد",
        no_files_hint: "ارفع المستندات لعرض النتائج"
      },
      chat: {
        user: "أنت",
        assistant: "أميرة"
      }
    }
  }
};

// Lấy ngôn ngữ đã lưu từ localStorage (chỉ trên client), fallback về 'vi'
const savedLng = typeof window !== 'undefined'
  ? (localStorage.getItem('mukjizat_saigoncert_lang') || 'vi')
  : 'vi';

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: savedLng,
    fallbackLng: 'vi',
    supportedLngs: ['en', 'vi', 'ms', 'ar'],
    ns: ['common'],
    defaultNS: 'common',
    interpolation: { escapeValue: false },
    react: { useSuspense: false },
  });

// Lưu ngôn ngữ vào localStorage mỗi khi thay đổi
i18n.on('languageChanged', (lng) => {
  if (typeof window !== 'undefined') {
    localStorage.setItem('mukjizat_saigoncert_lang', lng);
  }
});

if (typeof window !== 'undefined') {
  console.log('i18n initialized', i18n.language);
}

export default i18n;