#!/usr/bin/env python3

import io
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
from obfuscapk.exceptions import MissingDependencyError, ToolExecutionError
from typing import List


class Apktool(object):
    def __init__(self):
        self.logger = logging.getLogger(
            "{0}.{1}".format(__name__, self.__class__.__name__)
        )

        if "APKTOOL_PATH" in os.environ:
            self.apktool_path: str = os.environ["APKTOOL_PATH"]
        else:
            self.apktool_path: str = "apktool"

        full_apktool_path = shutil.which(self.apktool_path)

        # Make sure to use the full path of the executable (needed for cross-platform
        # compatibility).
        if full_apktool_path is None:
            raise RuntimeError(
                'Something is wrong with executable "{0}"'.format(self.apktool_path)
            )
        else:
            self.apktool_path = full_apktool_path

    def decode(
        self, apk_path: str, output_dir_path: str = None, force: bool = False
    ) -> str:
        # Check if the apk file to decode is a valid file.
        if not os.path.isfile(apk_path):
            self.logger.error('Unable to find file "{0}"'.format(apk_path))
            raise FileNotFoundError('Unable to find file "{0}"'.format(apk_path))

        # If no output directory is specified, use a new directory in the same
        # directory as the apk file to decode.
        if not output_dir_path:
            output_dir_path = os.path.join(
                os.path.dirname(apk_path),
                os.path.splitext(os.path.basename(apk_path))[0],
            )
            self.logger.debug(
                "No output directory provided, the result will be saved in the "
                "same directory as the input file, in a directory with the same "
                'name as the input file: "{0}"'.format(output_dir_path)
            )

        # If an output directory is provided, make sure that the path to that
        # directory exists (the final directory will be created by apktool).
        elif not os.path.isdir(os.path.dirname(output_dir_path)):
            self.logger.error(
                'Unable to find output directory "{0}", apktool won\'t be able to '
                'create the directory "{1}"'.format(
                    os.path.dirname(output_dir_path), output_dir_path
                )
            )
            raise NotADirectoryError(
                'Unable to find output directory "{0}", apktool won\'t be able to '
                'create the directory "{1}"'.format(
                    os.path.dirname(output_dir_path), output_dir_path
                )
            )

        # Inform the user if an existing output directory is provided without the
        # "force" flag.
        if os.path.isdir(output_dir_path) and not force:
            self.logger.error(
                'Output directory "{0}" already exists, use the "force" flag '
                "to overwrite".format(output_dir_path)
            )
            raise FileExistsError(
                'Output directory "{0}" already exists, use the "force" flag '
                "to overwrite".format(output_dir_path)
            )

        decode_cmd: List[str] = [
            self.apktool_path,
            "--frame-path",
            tempfile.gettempdir(),
            "d",
            apk_path,
            "-o",
            output_dir_path,
        ]

        if force:
            decode_cmd.insert(4, "--force")

        try:
            self.logger.info(
                'Running decode command "{0}"'.format(" ".join(decode_cmd))
            )
            # A new line character is sent as input since newer versions of Apktool
            # have an interactive prompt on Windows where the user should press a key.
            output = subprocess.check_output(
                decode_cmd, stderr=subprocess.STDOUT, input=b"\n"
            ).strip()
            if b"Exception in thread " in output:
                # Report exception raised in Apktool.
                raise subprocess.CalledProcessError(1, decode_cmd, output)
            return output.decode(errors="replace")
        except subprocess.CalledProcessError as e:
            self.logger.error(
                "Error during decode command: {0}".format(
                    e.output.decode(errors="replace") if e.output else e
                )
            )
            raise
        except Exception as e:
            self.logger.error("Error during decoding: {0}".format(e))
            raise

    def build(
        self, source_dir_path: str, output_apk_path: str = None, use_aapt2: bool = False
    ) -> str:
        # Check if the input directory exists.
        if not os.path.isdir(source_dir_path):
            self.logger.error(
                'Unable to find source directory "{0}"'.format(source_dir_path)
            )
            raise NotADirectoryError(
                'Unable to find source directory "{0}"'.format(source_dir_path)
            )

        # If no output apk path is specified, the new apk will be saved in the
        # default path: <source_dir_path>/dist/<source_dir_name>.apk
        if not output_apk_path:
            output_apk_path = os.path.join(
                source_dir_path,
                "dist",
                "{0}.apk".format(os.path.basename(source_dir_path)),
            )
            self.logger.debug(
                "No output apk path provided, the new apk will be saved in the "
                'default path: "{0}"'.format(output_apk_path)
            )

        build_cmd: List[str] = [
            self.apktool_path,
            "--frame-path",
            tempfile.gettempdir(),
            "b",
            "--force-all",
            source_dir_path,
            "-o",
            output_apk_path,
        ]

        if use_aapt2:
            build_cmd.insert(-2, "--use-aapt2")

        try:
            self.logger.info('Running build command "{0}"'.format(" ".join(build_cmd)))
            # A new line character is sent as input since newer versions of Apktool
            # have an interactive prompt on Windows where the user should press a key.
            output = subprocess.check_output(
                build_cmd, stderr=subprocess.STDOUT, input=b"\n"
            ).strip()
            if (
                b"brut.directory.PathNotExist: " in output
                or b"Exception in thread " in output
            ):
                # Report exception raised in Apktool.
                raise subprocess.CalledProcessError(1, build_cmd, output)

            if not os.path.isfile(output_apk_path):
                raise FileNotFoundError(
                    '"{0}" was not built correctly. Apktool output:\n{1}'.format(
                        output_apk_path, output.decode(errors="replace")
                    )
                )

            return output.decode(errors="replace")
        except subprocess.CalledProcessError as e:
            self.logger.error(
                "Error during build command: {0}".format(
                    e.output.decode(errors="replace") if e.output else e
                )
            )
            raise
        except Exception as e:
            self.logger.error("Error during building: {0}".format(e))
            raise


#새롭게 정의한 예외 클래스들을 가지고 옴
#예외 클래스가 없을 경우를 대비해 임시 정의도 포함
try:
    from obfuscapk.exceptions import MissingDependencyError,ToolExecutionError
except ImportError:
    class MissingDependencyError(Exception): pass
    class ToolExecutionError(Exception): pass    


class Zipalign(object):
    #MissingDependecyError 테스트
    raise MissingDependencyError(tool_name="zipalign(강제 테스트 진행)")
    def __init__(self):
        self.logger = logging.getLogger(
            "{0}.{1}".format(__name__, self.__class__.__name__)
        )

        if "ZIPALIGN_PATH" in os.environ:
            self.zipalign_path: str = os.environ["ZIPALIGN_PATH"]
        else:
            self.zipalign_path: str = "zipalign"

       #shutil.which으로 zipalign 경로 미리 확인
        full_zipalign_path = shutil.which(self.zipalign_path)

        # Make sure to use the full path of the executable (needed for cross-platform
        # compatibility).

        #zipalign 경로 확인
        if full_zipalign_path is None:
            #없으면 RuntimeError 발생

           
            #[고도화 1](zipalign이 없다는 건 Android SDK Build-Tools가 설치되지 않았다는 뜻이므로
            #사용자에게 설치 안내 메시지 제공하는 전용 예외 발생
            raise MissingDependencyError(
               tool_name="zipalign"
                
            )
        
        else:
            #zipalign 경로 있으면 전체 경로 저장
            self.zipalign_path = full_zipalign_path


#obfuscation.py의 lign_obfuscated_apk()에서  zipalign.align(self.obfuscated_apk_path)을 통해 호출되는 부분
    #apk_path: 정렬할 apk 파일 경로
    #출력: str. zipalign 명령어가 성공정으로 실행되었을 때 내뱉는 "성공 로그" 반환
    def align(self, apk_path: str) -> str:
       

        #zipaglin을 실행하기 전에, 입력받은 apk 파일 존재 여부 확인
        if not os.path.isfile(apk_path):
            self.logger.error('Unable to find file "{0}"'.format(apk_path))
            #파일이 없으면 raise 발생시켜 프로그램 즉시 안전하게 중단시킴
            raise FileNotFoundError('Unable to find file "{0}"'.format(apk_path))

        # Since zipalign cannot be run inplace, a temp file will be created.
       # 임시로 사용할 apk 복사본 경로 생성
        apk_copy_path = "{0}.copy.apk".format(
            os.path.join(
                os.path.dirname(apk_path),
                os.path.splitext(os.path.basename(apk_path))[0],
            )
        )

#이제부터 작업 시작
        try:
            #apk_path(원본 apk 파일)을 apk_copy_path(임시 복사본 )로 복사
            apk_copy_path = shutil.copy2(apk_path, apk_copy_path)

#zipalign 명령어 조립 및 실행

#algin_cmd: subprocess로 실행할 zipalign 명령어 리스트
            align_cmd = [
                self.zipalign_path,
                "-p", #apk 내부의 .so(네이티브 라이브러리) 파일들도 정렬
                "-v", #자세한 실행 로그 출력
                "-f", #출력 파일이 이미 존재하면 강제로 덮어쓰기
                "4", #4바이트 경계로 정렬
                apk_copy_path, #입력 파일: 임시 복사본(예: app.copy.apk)
                apk_path,   #출력 파일: 원본 apk 파일 경로(덮어쓰기) 예: app.apk
            ] #zipalign은 app.copy.apk을 읽어서, 정렬된 버전을  app.apk에 덮어쓴다.

            self.logger.info('Running align command "{0}"'.format(" ".join(align_cmd)))
            
            result = subprocess.run(
                align_cmd,
                capture_output=True, #stdout, stderr 캡처
                text=True,           #출력을 문자열로 받음
                check=False,  #종료코드 0이 아닐 때 수동으로 예외 처리

            )
        #[고도화 2] return code로 성공/실패 수동 확인
       #원래는  suvprocess.CalledProcessError 로 예외처리 => 이제는 ToolExecutionError 로 예외처리
       #zipalign이 실패했을 때(종료코드 1이상) 발생하는 예외 처리
            if result.returncode != 0:
                error_details = result.stderr.strip()
                self.logger.error(
                    "Zipalign 실행 실패.Details: {0}".format(error_details)
                )
                raise ToolExecutionError(
                    tool_name="zipalign",
                    details=error_details)
            #성공 시
            #zipalign 명령어가 성공적으로 실행되면(종료코드 0), 그 출력(stdout) 반환
            return result.stdout.strip()
        
        #[고도화 3]: OS관련 시스템 호출 중 오류 발생 시 예외 처리(OSError)

        #FileNotFoundError(파일이 존재하지 않을 때),PermissionError(접근권한이 없을 때) 등
        except(OSError) as e:
            self.logger.error("Error during aligning (file error): {0}".format(e))

            raise # 상위 호출자 obfuscation.align_obfuscated_apk()에게 예외 재발생시켜 알림
        

        #zipalign 실패 외의 예상치 못한 다른 예외 발생시
        except Exception as e:
            self.logger.error("Error during aligning: {0}".format(e))
            raise

        #오류가 나든 안나든 실행
        finally:
            # Remove the temp file used for zipalign.
            if os.path.isfile(apk_copy_path):
                os.remove(apk_copy_path) #임시로 만들었던 app.copy.apk 파일이 남아있으면 삭제


class ApkSigner(object):
    def __init__(self):
        self.logger = logging.getLogger(
            "{0}.{1}".format(__name__, self.__class__.__name__)
        )

        if "APKSIGNER_PATH" in os.environ:
            self.apksigner_path: str = os.environ["APKSIGNER_PATH"]
        else:
            self.apksigner_path: str = "apksigner"

        full_apksigner_path = shutil.which(self.apksigner_path)

        # Make sure to use the full path of the executable (needed for cross-platform
        # compatibility).
        if full_apksigner_path is None:
            raise RuntimeError(
                'Something is wrong with executable "{0}"'.format(self.apksigner_path)
            )
        else:
            self.apksigner_path = full_apksigner_path

    def sign(
        self,
        apk_path: str,
        keystore_file_path: str,
        keystore_password: str,
        key_alias: str,
        key_password: str = None,
    ) -> str:
        # Check if the apk file to sign is a valid file.
        if not os.path.isfile(apk_path):
            self.logger.error('Unable to find file "{0}"'.format(apk_path))
            raise FileNotFoundError('Unable to find file "{0}"'.format(apk_path))

        sign_cmd: List[str] = [
            self.apksigner_path,
            "sign",
            "-v",
            "--ks",
            keystore_file_path,
            "--ks-key-alias",
            key_alias,
            "--ks-pass",
            f"pass:{keystore_password}",
            apk_path,
        ]

        if key_password:
            sign_cmd.insert(-1, "--key-pass")
            sign_cmd.insert(-1, f"pass:{key_password}")

        try:
            self.logger.info('Running sign command "{0}"'.format(" ".join(sign_cmd)))
            output = subprocess.check_output(sign_cmd, stderr=subprocess.STDOUT).strip()
            return output.decode(errors="replace")
        except subprocess.CalledProcessError as e:
            self.logger.error(
                "Error during sign command: {0}".format(
                    e.output.decode(errors="replace") if e.output else e
                )
            )
            raise
        except Exception as e:
            self.logger.error("Error during signing: {0}".format(e))
            raise

    def resign(
        self,
        apk_path: str,
        keystore_file_path: str,
        keystore_password: str,
        key_alias: str,
        key_password: str = None,
    ) -> str:
        # If present, delete the old signature of the apk and then sign it with the
        # new signature. Since Python doesn't allow directly deleting a file inside an
        # archive, an OS independent solution is to create a new archive without
        # including the signature files.

        try:
            unsigned_apk_buffer = io.BytesIO()

            with zipfile.ZipFile(apk_path, "r") as current_apk:
                # Check if the current apk is already signed.
                if any(
                    entry.filename.startswith("META-INF/")
                    for entry in current_apk.infolist()
                ):
                    self.logger.info(
                        'Removing current signature from apk "{0}"'.format(apk_path)
                    )

                    # Create a new in-memory archive without the signature.
                    with zipfile.ZipFile(
                        unsigned_apk_buffer, "w"
                    ) as unsigned_apk_zip_buffer:
                        for entry in current_apk.infolist():
                            if not entry.filename.startswith("META-INF/"):
                                unsigned_apk_zip_buffer.writestr(
                                    entry, current_apk.read(entry.filename)
                                )

                    # Write the in-memory archive to disk.
                    with open(apk_path, "wb") as unsigned_apk:
                        unsigned_apk.write(unsigned_apk_buffer.getvalue())

        except Exception as e:
            self.logger.error(
                "Error during the removal of the old signature: {0}".format(e)
            )
            raise

        return self.sign(
            apk_path, keystore_file_path, keystore_password, key_alias, key_password
        )
