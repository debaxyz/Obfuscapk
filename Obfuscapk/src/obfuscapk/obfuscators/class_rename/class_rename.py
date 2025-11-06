# Python3 인터프리터를 사용하여 스크립트를 실행하도록 지정
#!/usr/bin/env python3
#로깅 모듈
import logging
#OS 관련 모듈
import os
#정규 표현식 모듈
import re
#XML 처리 모듈

import xml.etree.cElementTree as Xml
from typing import List, Set, Dict, Union
from xml.etree.cElementTree import Element

# Obfuscapk 난독화 카테고리 모듈
from obfuscapk import obfuscator_category

# Obfuscapk 유틸리티 모듈
from obfuscapk import util

# Obfuscapk Obfuscation 클래스
from obfuscapk.obfuscation import Obfuscation


# ClassRename 클래스 요약:
# Smali 코드 내 클래스 이름을 난독화하고, Manifest와 XML 파일에서의
# 클래스 사용 부분까지 일괄적으로 변경하여 역공학을 어렵게 만드는
# 난독화 클래스


class ClassRename(obfuscator_category.IRenameObfuscator):
    
# 클래스 생성자
    def __init__(self):
        #로거 생성
        self.logger = logging.getLogger(
            "{0}.{1}".format(__name__, self.__class__.__name__)
        )
        #상위 클래스 초기화
        super().__init__()
        # Subclass 이름 패턴 정의
        self.subclass_name_pattern = re.compile(
            r'\s+name\s=\s"(?P<subclass_name>\S+?)"', re.UNICODE
        )

# 문자열 패턴 정의
        self.string_pattern = re.compile(r'"(?P<string_value>\S+?)"', re.UNICODE)
        # 클래스명 분할 패턴 정의
        self.split_class_pattern = re.compile(r"[/$]")
        # 패키지명 및 암호화된 패키지명
        self.package_name: Union[str, None] = None
        self.encrypted_package_name: Union[str, None] = None
        self.ignore_package_names = []

 # Smali 파일별 클래스 이름 매핑
        # Will be populated before running the class rename obfuscator.
        self.class_name_to_smali_file: dict = {}

# 클래스/패키지명 난독화
    def encrypt_identifier(self, identifier: str) -> str:
        identifier_md5 = util.get_string_md5(identifier)
        return "p{0}".format(identifier_md5.lower()[:8])

# 클래스 이름의 슬래시와 $를 .으로 변환
    def slash_to_dot_notation_for_classes(
        self, rename_transformations: Dict[str, str]
    ) -> Dict[str, str]:
        dot_rename_transformations: Dict[str, str] = {}

        # Remove leading L and trailing ; from class names and replace / and $ with .
        for old_name, new_name in rename_transformations.items():
            dot_rename_transformations[
                old_name[1:-1].replace("/", ".").replace("$", ".")
            ] = (new_name[1:-1].replace("/", ".").replace("$", "."))

        return dot_rename_transformations

# 패키지명 변환 및 Manifest 갱신
    def transform_package_name(self, manifest_xml_root: Element):
       #패키지명을 암호화
        self.encrypted_package_name = ".".join(
            [self.encrypt_identifier(token) for token in self.package_name.split(".")]
        )
 # Manifest 파일에 패키지명 변경
        # Rename package name in manifest file.
        manifest_xml_root.set("package", self.encrypted_package_name)
        manifest_xml_root.set(
            "{http://schemas.android.com/apk/res/android}sharedUserId",
            "{0}.uid.shared".format(util.get_random_string(16)),
        )
# Smali 파일 내 클래스 선언 난독화
    def rename_class_declarations(
        self, smali_files: List[str], interactive: bool = False
    ) -> dict:
        renamed_classes = {}

        # Search for class declarations that can be renamed.
        for smali_file in util.show_list_progress(
            smali_files,
            interactive=interactive,
            description="Renaming class declarations",
        ):
            annotation_flag = False
            with util.inplace_edit_file(smali_file) as (in_file, out_file):
                skip_remaining_lines = False
                class_name = None
                r_class = False
                for line in in_file:
                    if skip_remaining_lines:
                        out_file.write(line)
                        continue

                    if not class_name:
                        class_match = util.class_pattern.match(line)
                        if class_match:
                            class_name = class_match.group("class_name")
# 난독화 제외 클래스 확인
                            ignore_class = class_name.startswith(
                                tuple(self.ignore_package_names)
                            )

 # 클래스명을 토큰별로 분리하고 암호화
                            # Split class name to its components and encrypt them.
                            class_tokens = self.split_class_pattern.split(
                                class_name[1:-1]
                            )

                            encrypted_class_name = "L"
                            separator_index = 1
                            for token in class_tokens:
                                separator_index += len(token)
                                if token == "R":
                                    r_class = True
                                if token.isdigit():
                                    encrypted_class_name += (
                                        token + class_name[separator_index]
                                    )
                                elif not r_class and not ignore_class:
                                    encrypted_class_name += (
                                        self.encrypt_identifier(token)
                                        + class_name[separator_index]
                                    )
                                else:
                                    encrypted_class_name += (
                                        token + class_name[separator_index]
                                    )
                                separator_index += 1

 # Smali 파일에 암호화된 클래스명 반영
                            out_file.write(
                                line.replace(class_name, encrypted_class_name)
                            )

                            renamed_classes[class_name] = encrypted_class_name
                            continue
 # 내부 클래스 어노테이션 처리
                    if (
                        line.strip()
                        == ".annotation system Ldalvik/annotation/InnerClass;"
                    ):
                        annotation_flag = True
                        out_file.write(line)
                        continue

                    if annotation_flag and 'name = "' in line:
                          # Subclass 이름도 암호화
                        # Subclasses have to be renamed as well.
                        subclass_match = self.subclass_name_pattern.match(line)
                        if subclass_match and not r_class:
                            subclass_name = subclass_match.group("subclass_name")
                            out_file.write(
                                line.replace(
                                    subclass_name,
                                    self.encrypt_identifier(subclass_name),
                                )
                            )
                        else:
                            out_file.write(line)
                        continue

                    if line.strip() == ".end annotation":
                        annotation_flag = False
                        out_file.write(line)
                        continue
 # 메서드 선언 이후 클래스 정의는 더 이상 없음
                    # Method declaration reached, no more class definitions in
                    # this file.
                    if line.startswith(".method "):
                        skip_remaining_lines = True
                        out_file.write(line)
                    else:
                        out_file.write(line)

        return renamed_classes
    
 # Smali 파일 내 클래스 사용 부분 난독화
    def rename_class_usages_in_smali(
        self,
        smali_files: List[str],
        rename_transformations: dict,
        interactive: bool = False,
    ):
        dot_rename_transformations = self.slash_to_dot_notation_for_classes(
            rename_transformations
        )
 # 패키지명 추가
        # Add package name.
        dot_rename_transformations[self.package_name] = self.encrypted_package_name

        for smali_file in util.show_list_progress(
            smali_files,
            interactive=interactive,
            description="Renaming class usages in smali files",
        ):
            with util.inplace_edit_file(smali_file) as (in_file, out_file):
                for line in in_file:
                    # 문자열로 사용된 클래스명 변경
                    # Rename classes used as strings with . instead of /.
                    string_match = self.string_pattern.search(line)
                    if (
                        string_match
                        and string_match.group("string_value")
                        in dot_rename_transformations
                    ):
                        line = line.replace(
                            string_match.group("string_value"),
                            dot_rename_transformations[
                                string_match.group("string_value")
                            ],
                        )
 # Annotation 문자열 처리
                    # Sometimes classes are used in annotations as strings
                    # without trailing ;
                    if (
                        string_match
                        and "{0};".format(string_match.group("string_value"))
                        in rename_transformations
                    ):
                        line = line.replace(
                            string_match.group("string_value"),
                            rename_transformations[
                                "{0};".format(string_match.group("string_value"))
                            ][:-1],
                        )
 # 클래식 Smali 문법으로 사용된 클래스명 변경
                    # Rename classes used with the "classic" syntax
                    # (leading L and trailing ;).
                    class_names = util.class_name_pattern.findall(line)
                    for class_name in class_names:
                        if class_name in rename_transformations:
                            line = line.replace(
                                class_name, rename_transformations[class_name]
                            )

                    out_file.write(line)
# XML 파일 내 클래스 사용 부분 난독화
    def rename_class_usages_in_xml(
        self,
        xml_files: List[str],
        rename_transformations: dict,
        interactive: bool = False,
    ):
        dot_rename_transformations = self.slash_to_dot_notation_for_classes(
            rename_transformations
        )
# 패키지명 추가
        # Add package name.
        dot_rename_transformations[self.package_name] = self.encrypted_package_name

        for xml_file in util.show_list_progress(
            xml_files,
            interactive=interactive,
            description="Renaming class usages in xml files",
        ):
             # XML 파일 읽기
            with open(xml_file, "r", encoding="utf-8") as current_file:
                file_content = current_file.read()
  # 길이가 긴 이름부터 교체
            # Replace strings from longest to shortest (to avoid replacing
            # partial strings).
            for old_name in sorted(dot_rename_transformations, reverse=True, key=len):
                file_content = file_content.replace(
                    old_name, dot_rename_transformations[old_name]
                )
 # Activity명에 패키지명 제외된 경우 처리
                # Activity without package name (".ActivityName")
                if (
                    '"{0}"'.format(old_name.replace(self.package_name, ""))
                    in file_content
                ):
                    file_content = file_content.replace(
                        '"{0}"'.format(old_name.replace(self.package_name, "")),
                        '"{0}"'.format(
                            dot_rename_transformations[old_name].replace(
                                self.encrypted_package_name, ""
                            )
                        ),
                    )
 # 변경된 내용 쓰기
            with open(xml_file, "w", encoding="utf-8") as current_file:
                current_file.write(file_content)
  # 난독화 실행
    def obfuscate(self, obfuscation_info: Obfuscation):
        self.logger.info('Running "{0}" obfuscator'.format(self.__class__.__name__))

        try:
            # Android namespace 등록
            Xml.register_namespace(
                "android", "http://schemas.android.com/apk/res/android"
            )

            xml_parser = Xml.XMLParser(encoding="utf-8")
            manifest_tree = Xml.parse(
                obfuscation_info.get_manifest_file(), parser=xml_parser
            )
            manifest_root = manifest_tree.getroot()

            # 패키지명 가져오기

            self.package_name = manifest_root.get("package")
            if not self.package_name:
                raise Exception(
                    "Unable to extract package name from application manifest"
                )

# Smali 파일별 클래스 이름 매핑
            # Get a mapping between class name and smali file path.
            for smali_file in util.show_list_progress(
                obfuscation_info.get_smali_files(),
                interactive=obfuscation_info.interactive,
                description="Class name to smali file mapping",
            ):
                with open(smali_file, "r", encoding="utf-8") as current_file:
                    class_name = None
                    for line in current_file:
                        if not class_name:
                            # Every smali file contains a class.
                            class_match = util.class_pattern.match(line)
                            if class_match:
                                self.class_name_to_smali_file[
                                    class_match.group("class_name")
                                ] = smali_file
                                break
  # Manifest 내 패키지명 갱신
            self.transform_package_name(manifest_root)
 # Manifest 파일 쓰기
            # Write the changes into the manifest file.
            manifest_tree.write(obfuscation_info.get_manifest_file(), encoding="utf-8")
# XML 파일 수집
            xml_files: Set[str] = set(
                os.path.join(root, file_name)
                for root, dir_names, file_names in os.walk(
                    obfuscation_info.get_resource_directory()
                )
                for file_name in file_names
                if file_name.endswith(".xml")
                and (
                    "layout" in root or "xml" in root
                )  # Only res/layout-*/ and res/xml-*/ folders.
            )
            xml_files.add(obfuscation_info.get_manifest_file())

            # TODO: use the following code to rename only the classes declared in
            #  application's package.

            # package_smali_files: Set[str] = set(
            #     smali_file
            #     for class_name, smali_file in self.class_name_to_smali_file.items()
            #     if class_name[1:].startswith(self.package_name.replace(".", "/"))
            # )
            #
            # # Rename the classes declared in the application's package.
            # class_rename_transformations = self.rename_class_declarations(
            #     list(package_smali_files), obfuscation_info.interactive
            # )

 # Ignore 패키지 목록 가져오기
            # Get user defined ignore package list.
            self.ignore_package_names = obfuscation_info.get_ignore_package_names()
   # 모든 Smali 파일 내 클래스명 난독화
            # Rename all classes declared in smali files.
            class_rename_transformations = self.rename_class_declarations(
                obfuscation_info.get_smali_files(), obfuscation_info.interactive
            )
 # Smali 파일 내 사용 부분 난독화
            # Update renamed classes through all the smali files.
            self.rename_class_usages_in_smali(
                obfuscation_info.get_smali_files(),
                class_rename_transformations,
                obfuscation_info.interactive,
            )
 # XML 파일 내 사용 부분 난독화
            # Update renamed classes through all the xml files.
            self.rename_class_usages_in_xml(
                list(xml_files),
                class_rename_transformations,
                obfuscation_info.interactive,
            )

        except Exception as e:
               # 예외 발생 시 로그
            self.logger.error(
                'Error during execution of "{0}" obfuscator: {1}'.format(
                    self.__class__.__name__, e
                )
            )
            raise

        finally:
             # 사용된 난독화기록에 추가
            obfuscation_info.used_obfuscators.append(self.__class__.__name__)
