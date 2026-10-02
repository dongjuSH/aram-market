// 카카오(다음) 우편번호 검색을 화면 안 모달에 띄워 우편번호·기본 주소를 돌려주는 창

import { useEffect, useRef, useState } from 'react'

const SCRIPT_URL = 'https://t1.kakaocdn.net/mapjsapi/bundle/postcode/prod/postcode.v2.js'

let scriptPromise = null

// 우편번호 스크립트를 한 번만 불러옴(window.kakao와 window.daum은 같은 객체)
function loadPostcodeScript() {
  if (window.kakao?.Postcode) return Promise.resolve(window.kakao)
  scriptPromise ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT_URL
    script.onload = () => resolve(window.kakao)
    script.onerror = () => {
      scriptPromise = null
      reject(new Error('주소 검색을 불러오지 못했습니다. 네트워크를 확인한 뒤 다시 시도해 주세요.'))
    }
    document.head.appendChild(script)
  })
  return scriptPromise
}

// 도로명 주소에 법정동·아파트 건물명을 괄호로 덧붙임(카카오 공식 예제 규칙)
function toAddress(data) {
  if (data.userSelectedType !== 'R') return data.jibunAddress || data.address
  const extras = []
  if (data.bname && /[동로가]$/.test(data.bname)) extras.push(data.bname)
  if (data.buildingName && data.apartment === 'Y') extras.push(data.buildingName)
  return extras.length ? `${data.roadAddress} (${extras.join(', ')})` : data.roadAddress
}

// 열려 있는 동안만 부모가 그리며, 주소를 고르면 onSelect({ postcode, address }) 호출
function PostcodeSearchModal({ onClose, onSelect }) {
  const containerRef = useRef(null)
  const closeRef = useRef(null)
  const [error, setError] = useState('')
  const onSelectRef = useRef(onSelect) // 부모가 다시 그려져도 검색창을 새로 만들지 않도록 최신 콜백만 보관

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  // 모달이 열리면 검색창을 그림
  useEffect(() => {
    let isActive = true
    closeRef.current?.focus()
    loadPostcodeScript()
      .then((kakao) => {
        if (!isActive || !containerRef.current) return
        new kakao.Postcode({
          width: '100%',
          height: '100%',
          oncomplete: (data) => onSelectRef.current({ postcode: data.zonecode, address: toAddress(data) }),
        }).embed(containerRef.current)
      })
      .catch((loadError) => isActive && setError(loadError.message))
    return () => {
      isActive = false
    }
  }, [])

  // Escape로 닫기
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  return (
    <div className="modal-overlay" role="presentation" onClick={(event) => event.target === event.currentTarget && onClose()}>
      <section className="postcode-modal" role="dialog" aria-modal="true" aria-labelledby="postcode-modal-title">
        <div className="postcode-modal__head">
          <h2 id="postcode-modal-title">주소 검색</h2>
          <button ref={closeRef} className="modal-close" type="button" aria-label="주소 검색 닫기" onClick={onClose}>
            <span aria-hidden="true" />
          </button>
        </div>
        {error ? <p className="postcode-modal__error" role="alert">{error}</p> : <div ref={containerRef} className="postcode-modal__frame" />}
      </section>
    </div>
  )
}

export default PostcodeSearchModal
