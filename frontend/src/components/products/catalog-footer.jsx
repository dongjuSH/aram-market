// 고객 상품 화면에 브랜드와 사업자 정보를 제공하는 공통 푸터

// 사이트 운영 정보를 제공하는 고객 푸터
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
            <span>재단법인 아람마켓 한국</span>
            <span>고유번호 123-45-67890</span>
            <span>대표자 김아람</span>
            <span>연락처 02-1234-5678</span>
            <span>이메일 info@arammarket.kr</span>
            <span>주소 서울특별시 마포구 아람로 12, 5층</span>
          </p>
          <small>Copyright © 2026 Aram Market Korea. All rights reserved.</small>
        </div>
      </div>
    </footer>
  )
}

export default CatalogFooter
