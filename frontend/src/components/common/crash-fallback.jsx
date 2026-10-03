// 렌더링 오류로 화면을 그릴 수 없을 때 빈 화면 대신 보여 주는 안내

// 화면 렌더링 중 예상하지 못한 오류가 나면 빈 화면 대신 보여 줄 안내
function CrashFallback() {
  return (
    <main className="auth-page">
      <section className="auth-panel auth-panel--login" role="alert">
        <header className="auth-header">
          <h1>일시적인 오류가 발생했습니다</h1>
          <p className="auth-description">페이지를 새로고침해 주세요. 문제가 계속되면 잠시 후 다시 이용해 주세요.</p>
        </header>
        <button className="primary-button" type="button" onClick={() => window.location.reload()}>새로고침</button>
      </section>
    </main>
  )
}

export default CrashFallback
