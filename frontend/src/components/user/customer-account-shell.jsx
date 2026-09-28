// 고객 계정 화면에서 메인 페이지와 동일한 헤더·푸터를 공유하는 레이아웃

import CatalogFooter from '../products/catalog-footer.jsx'
import CatalogHeader from '../products/catalog-header.jsx'


function CustomerAccountShell({ onNavigate, children, className = '' }) {
  return (
    <div className={`catalog-page customer-account-page${className ? ` ${className}` : ''}`}>
      <a className="catalog-skip-link" href="#catalog-main">본문 바로가기</a>
      <CatalogHeader onNavigate={onNavigate} />
      <main id="catalog-main" className="customer-account-main" tabIndex="-1">
        {children}
      </main>
      <CatalogFooter />
    </div>
  )
}

export default CustomerAccountShell
