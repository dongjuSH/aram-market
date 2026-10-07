// 고객 화면 공통 푸터: 브랜드와 포트폴리오용 테스트 사이트 안내

// 실제 사업자처럼 보이는 가상 정보 대신 테스트 사이트임을 알리는 고객 푸터
function CatalogFooter() {
  return (
    <footer className="catalog-footer">
      <div className="catalog-footer__inner">
        <div className="catalog-footer__brand">
          <img src="/assets/aram-market-fruit.svg" alt="" />
          <strong>아람 마켓</strong>
        </div>

        <div className="catalog-footer__information">
          <p>
            <span>포트폴리오용 테스트 사이트</span>
            <span>실제 판매·결제·배송은 이루어지지 않습니다</span>
            <span>결제는 토스페이먼츠 테스트 모드로만 동작합니다</span>
          </p>
          <small>© 2026 Aram Market · 개인 포트폴리오 프로젝트</small>
        </div>
      </div>
    </footer>
  )
}

export default CatalogFooter
