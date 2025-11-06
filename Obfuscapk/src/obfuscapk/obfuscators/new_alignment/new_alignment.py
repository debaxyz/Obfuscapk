
"""
NewAlignment 난독화 클래스
-----------------------------------
목적:
    - 난독화된 APK 파일을 정렬(alignment)하여 최적화.
    - APK 내부 데이터가 4바이트 경계에 정렬되도록 처리.
    - APK 실행 효율 향상 및 일부 분석 툴 탐지 회피 가능.

동작 방식:
    1. Obfuscation 객체의 align_obfuscated_apk() 호출.
    2. APK 내부 모든 파일의 정렬(alignment) 수행.
    3. 오류 발생 시 로그 기록 및 예외 발생.

특징:
    - 단순 난독화 후 최적화용 트리비얼 오브퍼케이터.
    - APK 실행 성능이나 일부 정적 분석 회피에 도움.
    - 직접 Smali나 XML을 수정하지 않음.

주의 사항:
    - 난독화 과정 후 APK에만 적용 가능.
    - align_obfuscated_apk()에서 예외 발생 시 APK 처리 실패.
"""
#!/usr/bin/env python3

import logging

from obfuscapk import obfuscator_category
from obfuscapk.obfuscation import Obfuscation


  
    ##  NewAlignment 클래스:
     ##   - 난독화된 APK 정렬(alignment) 수행
       ## - 실행 성능 최적화 및 일부 분석 회피
    

class NewAlignment(obfuscator_category.ITrivialObfuscator):
    
    def __init__(self):
        ## 로거 설정
        self.logger = logging.getLogger(
            "{0}.{1}".format(__name__, self.__class__.__name__)
        )
        #상위 클래스 초기화
        super().__init__()

#난독화 실행
    def obfuscate(self, obfuscation_info: Obfuscation):
        self.logger.info('Running "{0}" obfuscator'.format(self.__class__.__name__))

        try:
            #Obufscation 객체를 통해 APK 정렬 수행
            obfuscation_info.align_obfuscated_apk()
        except Exception as e:
            #오류 로그 기록 및 예외 발생
            self.logger.error(
                'Error during execution of "{0}" obfuscator: {1}'.format(
                    self.__class__.__name__, e
                )
            )
            raise

        finally:
            #사용된 난독화기록에 추가
            obfuscation_info.used_obfuscators.append(self.__class__.__name__)
