"""
Obfuscapk 의 예외처리 부재 문제를 해결하기 위한 파일

더 상세한 로그와 안정적인 오류 처리를 하기 위해 작성

"""

class ObfuscapkException(Exception):
    """Obfuscapk 관련 예외의 기본 클래스"""

    pass

#1. 도구 관련 오류
class ToolError(ObfuscapkException):
    """
    apktool, zipalign, jarsigner 등
    외부 도구 실행 중 발생한 오류를 나타내는 예외 클래스"""

    def __init__(self,tool_name: str, message: str):
        self.tool_name = tool_name
        self.message = message
        super().__init__(f"{tool_name} error: {message}")


class MissingDependencyError(ToolError):
    """
    Obfuscapk 실행에 필요한 외부 도구가 누락된 경우 발생하는 예외 클래스
    예: newalignment 난독화를 진햏아는데 zipalign 도구가 설치되지 않은 경우
    """

    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(tool_name,f"'{tool_name}' 을 찾을 수 없습니다.""PATH에 설치 및 추가되었는지 확인해주세요.")        

class ToolExecutionError(ToolError):
    """
    외부 도구 실행 중 0이 아닌 종료 코드를 반화하며 실패했을 때 발생
    예: zipalign이 손상된 apk 파일때문에 실행 실패
    
    """

    def __init__(self,tool_name:str, details:str):
        self.tool_name = tool_name
        #details는 도구가 stderr로 출력한 실제 오류 메세지
        self.details = details
        super().__init__(tool_name,f"'{tool_name}' 실행 중 오류 발생: {details}")


#2. 플러그인 관련 오류
class PluginError(ObfuscapkException):
    """난독화 플러그인 관련 오류를 나타내는 예외 클래스"""
    def __init__(self, plugin_name: str, message: str):
        self.plugin_name = plugin_name
        self.message = message
        super().__init__(f"Plugin '{plugin_name}' error: {message}")


#플러그인의 주 로직이 실패했을 때
class PluginExecutionError(PluginError):
    """
    난독화 플러그인의 실행 중 오류가 발생했을 때 발생하는 예외 클래스
    예: NewAlignment 플러그인이 APK 정렬 중 실패한 경우
    """

    def __init__(self, plugin_name: str, details: str):
        self.plugin_name = plugin_name
        #details는 플러그인이 기록한 실제 오류 메세지
        self.details = details
        super().__init__(plugin_name, f"'{plugin_name}' 실행 중 오류 발생: {details}")  

#SmailParsing이 실패했을 때(reorder 플러그인 등에서 사용)
#바로 프로그램이 죽는데 이 예외 클래스를 사용해서 어디서 파싱이 실패했는지 smail 파일 상세 정보 제공
class SmaliParsingError(PluginError):
    """
    Smali 코드 파싱 중 오류가 발생했을 때 발생하는 예외 클래스
    예: Reorder 플러그인이 Smali 파일을 파싱하는 도중 문법 오류를 발견한 경우
    """

    def __init__(self, plugin_name: str, file_path: str, details: str):
        self.plugin_name = plugin_name
        self.file_path = file_path
        self.details = details
        super().__init__(plugin_name, f"Smali 파일 '{file_path}' 파싱 중 오류 발생: {details}")        