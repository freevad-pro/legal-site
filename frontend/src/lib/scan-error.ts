// Маппинг технических ошибок Playwright / бэка в человекочитаемые фразы.
// Возвращаем и заголовок, и пометку, нужно ли показывать raw-текст под спойлером.

export interface HumanScanError {
  title: string;
  description: string | null;
  details: string | null;
}

const DEFAULT_DESCRIPTION =
  "Сайт не ответил, либо проверка завершилась с ошибкой. Попробуйте ещё раз позже.";

export function humanizeScanError(raw: string | null): HumanScanError {
  if (!raw || !raw.trim()) {
    return { title: "Не удалось проверить сайт", description: DEFAULT_DESCRIPTION, details: null };
  }

  const lower = raw.toLowerCase();

  if (lower.includes("err_timed_out") || lower.includes("timeout")) {
    return {
      title: "Сайт не отвечает",
      description: "Превышено время ожидания загрузки. Возможно, сайт перегружен или блокирует автоматические проверки.",
      details: raw,
    };
  }
  if (lower.includes("err_name_not_resolved") || lower.includes("getaddrinfo")) {
    return {
      title: "Адрес сайта не найден",
      description: "Не удалось определить IP по доменному имени. Проверьте, правильно ли введён URL.",
      details: raw,
    };
  }
  if (lower.includes("err_connection_refused")) {
    return {
      title: "Сервер отклонил подключение",
      description: "Сайт активно отказывается принимать соединения. Возможно, он не работает или закрыт для внешних запросов.",
      details: raw,
    };
  }
  if (lower.includes("err_connection_reset") || lower.includes("err_connection_closed")) {
    return {
      title: "Соединение сброшено",
      description: "Сайт прервал соединение во время загрузки. Попробуйте позже.",
      details: raw,
    };
  }
  if (lower.includes("err_cert") || lower.includes("ssl") || lower.includes("certificate")) {
    return {
      title: "Проблема с SSL-сертификатом",
      description: "У сайта недействительный или просроченный SSL-сертификат — проверка невозможна.",
      details: raw,
    };
  }
  if (lower.includes("err_too_many_redirects")) {
    return {
      title: "Слишком много перенаправлений",
      description: "Сайт уходит в бесконечный цикл редиректов.",
      details: raw,
    };
  }
  if (lower.includes("err_aborted")) {
    return {
      title: "Загрузка прервана",
      description: "Браузер прервал загрузку страницы.",
      details: raw,
    };
  }

  return { title: "Не удалось проверить сайт", description: DEFAULT_DESCRIPTION, details: raw };
}
