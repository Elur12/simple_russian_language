import { useEffect, useState } from "react";
import {
  analyzeText,
  deleteProfileToken,
  fetchUrlText,
  getProfileToken,
  loginUser,
  registerUser,
  saveProfileToken,
  type AnalysisResponse,
  type TokenStatus,
} from "./api/client";
import { TextAnalysisViewer } from "./components/TextAnalysisViewer";

type InputMode = "text" | "url";

export default function App() {
  const [accessToken, setAccessToken] = useState<string>(localStorage.getItem("access_token") || "");
  const [refreshToken, setRefreshToken] = useState<string>(localStorage.getItem("refresh_token") || "");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [inputMode, setInputMode] = useState<InputMode>("text");
  const [text, setText] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [fetchedTitle, setFetchedTitle] = useState<string | null>(null);
  const [fetchedUrl, setFetchedUrl] = useState<string | null>(null);

  const [tokenInput, setTokenInput] = useState("");
  const [tokenStatus, setTokenStatus] = useState<TokenStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchingUrl, setFetchingUrl] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);

  useEffect(() => {
    if (!accessToken) {
      setTokenStatus(null);
      return;
    }
    getProfileToken(accessToken)
      .then(setTokenStatus)
      .catch(() => setTokenStatus(null));
  }, [accessToken]);

  function switchInputMode(mode: InputMode) {
    setInputMode(mode);
    setError(null);
    setResult(null);
    if (mode === "text") {
      setFetchedTitle(null);
      setFetchedUrl(null);
    }
  }

  async function onFetchUrl() {
    const url = urlInput.trim();
    if (!url) {
      setError("Введите ссылку на страницу.");
      return;
    }
    if (!accessToken) {
      setError("Сначала войдите в аккаунт.");
      return;
    }

    setError(null);
    setFetchedTitle(null);
    setFetchedUrl(null);
    setFetchingUrl(true);
    setStatus("Загружаем страницу…");
    try {
      const data = await fetchUrlText(url, accessToken);
      setText(data.text);
      setFetchedTitle(data.title || null);
      setFetchedUrl(data.url);
      setStatus("Страница загружена. Текст доступен для редактирования.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить страницу.");
      setStatus(null);
    } finally {
      setFetchingUrl(false);
    }
  }

  async function onAnalyze() {
    setError(null);
    setResult(null);

    if (!text.trim()) {
      setError(inputMode === "url" ? "Сначала загрузите текст со страницы." : "Вставьте текст для анализа.");
      return;
    }
    if (!accessToken) {
      setError("Сначала войдите в аккаунт.");
      return;
    }
    if (!tokenStatus?.has_token) {
      setError("Сначала сохраните токен Yandex AI Studio в профиле.");
      return;
    }

    setLoading(true);
    setStatus("Анализируем текст. Это может занять до минуты.");
    try {
      const data = await analyzeText(text, accessToken);
      setResult(data);
      setStatus(
        `Анализ завершён. Найдено: ${data.summary.green} хорошо, ${data.summary.orange} требует правок, ${data.summary.red} переписать.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Неизвестная ошибка");
      setStatus(null);
    } finally {
      setLoading(false);
    }
  }

  async function onAuthSubmit() {
    setError(null);
    try {
      if (authMode === "register") {
        await registerUser({ username, email, password });
      }
      const tokens = await loginUser({ username, password });
      setAccessToken(tokens.access);
      setRefreshToken(tokens.refresh);
      localStorage.setItem("access_token", tokens.access);
      localStorage.setItem("refresh_token", tokens.refresh);
      setStatus(authMode === "register" ? "Регистрация и вход выполнены." : "Вход выполнен.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка авторизации");
    }
  }

  async function onSaveApiToken() {
    if (!accessToken) { setError("Сначала войдите в аккаунт."); return; }
    if (!tokenInput.trim()) { setError("Введите токен Yandex AI Studio."); return; }
    setError(null);
    try {
      const tokenState = await saveProfileToken(accessToken, tokenInput.trim());
      setTokenStatus(tokenState);
      setTokenInput("");
      setStatus("Токен Yandex AI Studio сохранён.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка сохранения токена");
    }
  }

  async function onDeleteApiToken() {
    if (!accessToken) { setError("Сначала войдите в аккаунт."); return; }
    setError(null);
    try {
      await deleteProfileToken(accessToken);
      setTokenStatus({ has_token: false });
      setStatus("Токен удалён.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка удаления токена");
    }
  }

  function onLogout() {
    setAccessToken("");
    setRefreshToken("");
    setTokenStatus(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    setStatus("Вы вышли из аккаунта.");
  }

  return (
    <>
      <a href="#main-content" className="skip-link">Перейти к основному содержимому</a>

      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {status || ""}
      </div>

      <main id="main-content" className="page" aria-busy={loading || fetchingUrl}>
        <section className="panel" aria-labelledby="app-title">
          <h1 id="app-title">Проверка на Простой язык</h1>
          <p>Вставьте текст или укажите ссылку на страницу — получите разметку по абзацам с советами по исправлению.</p>

          {!accessToken ? (
            <section aria-labelledby="auth-heading">
              <h2 id="auth-heading" className="sr-only">Авторизация</h2>
              <div className="auth-switch" role="group" aria-label="Режим входа">
                <button
                  type="button"
                  onClick={() => setAuthMode("login")}
                  aria-pressed={authMode === "login"}
                >
                  Вход
                </button>
                <button
                  type="button"
                  onClick={() => setAuthMode("register")}
                  aria-pressed={authMode === "register"}
                >
                  Регистрация
                </button>
              </div>

              <label htmlFor="username-input">Логин</label>
              <input
                id="username-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="username"
                autoComplete="username"
                autoCapitalize="none"
                spellCheck={false}
              />

              {authMode === "register" && (
                <>
                  <label htmlFor="email-input">Email</label>
                  <input
                    id="email-input"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="email@example.com"
                    autoComplete="email"
                    autoCapitalize="none"
                    spellCheck={false}
                  />
                </>
              )}

              <label htmlFor="password-input">Пароль</label>
              <input
                id="password-input"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Минимум 8 символов"
                autoComplete={authMode === "login" ? "current-password" : "new-password"}
                aria-describedby={authMode === "register" ? "password-hint" : undefined}
              />
              {authMode === "register" && (
                <p id="password-hint" className="field-hint">Не менее 8 символов.</p>
              )}

              <button type="button" onClick={onAuthSubmit}>
                {authMode === "login" ? "Войти" : "Зарегистрироваться"}
              </button>
            </section>
          ) : (
            <section aria-labelledby="account-heading">
              <h2 id="account-heading" className="sr-only">Аккаунт и токен Yandex AI Studio</h2>
              <p>
                Вы авторизованы. Токен обновления сохранён локально:{" "}
                <strong>{refreshToken ? "да" : "нет"}</strong>.
              </p>
              <button type="button" onClick={onLogout}>Выйти</button>

              <label htmlFor="api-token-input">Токен Yandex AI Studio</label>
              <input
                id="api-token-input"
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Введите токен и нажмите Сохранить"
                autoComplete="off"
                aria-describedby="api-token-status"
              />
              <div className="token-row" role="group" aria-label="Управление токеном">
                <button type="button" onClick={onSaveApiToken}>Сохранить токен</button>
                <button type="button" onClick={onDeleteApiToken}>Удалить токен</button>
              </div>
              <p id="api-token-status">
                Статус токена:{" "}
                {tokenStatus?.has_token
                  ? `сохранён (${tokenStatus.masked_token || "скрыт"})`
                  : "не сохранён"}
              </p>
            </section>
          )}

          <section aria-labelledby="input-heading">
            <h2 id="input-heading" className="sr-only">Выбор источника текста</h2>

            <div className="input-mode-toggle" role="group" aria-label="Источник текста">
              <button
                type="button"
                className={`mode-btn ${inputMode === "text" ? "mode-btn-active" : ""}`}
                onClick={() => switchInputMode("text")}
                aria-pressed={inputMode === "text"}
              >
                <span aria-hidden="true">✏️ </span>Текст
              </button>
              <button
                type="button"
                className={`mode-btn ${inputMode === "url" ? "mode-btn-active" : ""}`}
                onClick={() => switchInputMode("url")}
                aria-pressed={inputMode === "url"}
              >
                <span aria-hidden="true">🔗 </span>Ссылка на страницу
              </button>
            </div>

            {inputMode === "url" && (
              <div className="url-input-area">
                <label htmlFor="url-input">Ссылка на страницу</label>
                <div className="url-row">
                  <input
                    id="url-input"
                    type="url"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                    placeholder="https://example.com/article"
                    onKeyDown={(e) => e.key === "Enter" && onFetchUrl()}
                    autoComplete="url"
                    spellCheck={false}
                  />
                  <button
                    type="button"
                    onClick={onFetchUrl}
                    disabled={fetchingUrl}
                    className="btn-fetch"
                    aria-label={fetchingUrl ? "Загружаем страницу" : "Загрузить страницу по ссылке"}
                  >
                    {fetchingUrl ? (
                      <>
                        <span aria-hidden="true">…</span>
                        <span className="sr-only">Загружаем</span>
                      </>
                    ) : (
                      <>
                        <span aria-hidden="true">↓ </span>Загрузить
                      </>
                    )}
                  </button>
                </div>
                {fetchedUrl && (
                  <div className="fetched-meta">
                    {fetchedTitle && <span className="fetched-title">{fetchedTitle}</span>}
                    <a href={fetchedUrl} target="_blank" rel="noopener noreferrer" className="fetched-link">
                      {fetchedUrl}
                      <span className="sr-only"> (открывается в новой вкладке)</span>
                    </a>
                  </div>
                )}
              </div>
            )}

            {(inputMode === "text" || fetchedUrl) && (
              <>
                <label htmlFor="main-textarea">
                  {inputMode === "url" ? "Извлечённый текст (можно отредактировать)" : "Текст"}
                </label>
                <textarea
                  id="main-textarea"
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  rows={10}
                  placeholder={inputMode === "url" ? "Текст появится после загрузки страницы" : "Вставьте текст для анализа"}
                  spellCheck={true}
                  aria-describedby="analyze-hint"
                />
                <p id="analyze-hint" className="field-hint">
                  Абзацы разделяйте пустой строкой. После анализа каждый абзац получит оценку и предложения по правкам.
                </p>
              </>
            )}

            <button
              type="button"
              disabled={loading || fetchingUrl}
              onClick={onAnalyze}
            >
              {loading ? "Анализируем…" : "Запустить анализ"}
            </button>
          </section>

          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </section>

        {result && (
          <TextAnalysisViewer
            analysisResult={result}
            originalText={text}
            sourceTitle={fetchedTitle}
            sourceUrl={fetchedUrl}
          />
        )}
      </main>
    </>
  );
}
