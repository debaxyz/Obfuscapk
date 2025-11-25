#!/usr/bin/env python3

import logging
import os
import re
from typing import List, Dict

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from obfuscapk import obfuscator_category
from obfuscapk import util
from obfuscapk.obfuscation import Obfuscation
from obfuscapk.exceptions import PluginExecutionError


class LibEncryption(obfuscator_category.IEncryptionObfuscator):
    def __init__(self):
        self.logger = logging.getLogger(
            "{0}.{1}".format(__name__, self.__class__.__name__)
        )
        super().__init__()

        self.encryption_secret = "This-key-need-to-be-32-character"

    def obfuscate(self, obfuscation_info: Obfuscation):
        self.logger.info('Running "{0}" obfuscator'.format(self.__class__.__name__))

        self.encryption_secret = obfuscation_info.encryption_secret
        try:
            native_libs = obfuscation_info.get_native_lib_files()
            
            #고도화 (.so 파일이 없는 어플리케이션도 있을 시 없으면 바로 종료=> 시간 절약)
            if not native_libs:
                self.logger.debug("No native libraries (.so) found. Skipping LibEncryption obfuscator.")
                return
            
            native_lib_invoke_pattern = re.compile(
                r"\s+invoke-static\s{(?P<invoke_pass>[vp0-9]+)},\s"
                r"Ljava/lang/System;->loadLibrary\(Ljava/lang/String;\)V"
            )

            encrypted_to_original_mapping: Dict[str, str] = {}

            if native_libs:
                for smali_file in util.show_list_progress(
                    obfuscation_info.get_smali_files(),
                    interactive=obfuscation_info.interactive,
                    description="Encrypting native libraries",
                ):  
                    #고도화 Hilt 생성 코드나 외부 라이브러리는 제외(안정성을 위해)
                    if "Hilt_" in smali_file or "/androidx/" in smali_file:
                        continue

                    self.logger.debug(
                        "Replacing native libraries with encrypted native libraries "
                        'in file "{0}"'.format(smali_file)
                    )

                    with open(smali_file, "r", encoding="utf-8") as current_file:
                        lines = current_file.readlines()

                    class_name = None

                    local_count = 16

                    # Names of the loaded libraries.
                    lib_names: List[str] = []

                    editing_constructor = False
                    start_index = 0

                    #고도화를 위해 파일 수정 여부를 추척하는 플래그 설정
                    file_modified = False

                    for line_number, line in enumerate(lines):
                        if not class_name:
                            class_match = util.class_pattern.match(line)
                            if class_match:
                                class_name = class_match.group("class_name")
                                continue

                        # Native libraries should be loaded inside static constructors.
                        if (
                            line.startswith(".method static constructor <clinit>()V")
                            and not editing_constructor
                        ):
                            # Entering static constructor.
                            editing_constructor = True
                            start_index = line_number + 1
                            local_match = util.locals_pattern.match(
                                lines[line_number + 1]
                            )
                            if local_match:
                                local_count = int(local_match.group("local_count"))
                                if local_count <= 15:
                                    # An additional register is needed for the
                                    # encryption.
                                    local_count += 1
                                    lines[line_number + 1] = "\t.locals {0}\n".format(
                                        local_count
                                    )
                                    continue
                                else:
                                    #고도화(레지스터 부족 시 로그 남기고 해당 메서드 포기)
                                    self.logger.warning(
                                       f"Skipping encryption in {class_name}: "
                                       f"Too many locals ({local_count}). Max is 15."
                                        ) 
                                    break

                            # For some reason the locals declaration was not found where
                            # it should be, so assume the local registers are all used
                            # (we can't add any instruction here).
                            break

                        elif line.startswith(".end method") and editing_constructor:
                            # Only one static constructor per class.
                            break

                        elif editing_constructor:
                            # Inside static constructor.
                            invoke_match = native_lib_invoke_pattern.match(line)
                            if invoke_match:
                                # Native library load instruction. Iterate the
                                # constructor lines backwards in order to find the
                                # string containing the name of the loaded library.
                                for l_num in range(line_number - 1, start_index, -1):
                                    string_match = util.const_string_pattern.match(
                                        lines[l_num]
                                    )
                                    if string_match and string_match.group(
                                        "register"
                                    ) == invoke_match.group("invoke_pass"):
                                        # Native library string declaration.
                                        lib_names.append(string_match.group("string"))

                                # Static constructors take no parameters, so the highest
                                # register is v<local_count - 1>.
                                lines[line_number] = (
                                    "\tconst-class v{class_register_num}, "
                                    "{class_name}\n\n"
                                    "\tinvoke-static {{v{class_register_num}, "
                                    "{original_register}}}, "
                                    "Lcom/decryptassetmanager/DecryptAsset;->"
                                    "loadEncryptedLibrary("
                                    "Ljava/lang/Class;Ljava/lang/String;)V\n".format(
                                        class_name=class_name,
                                        original_register=invoke_match.group(
                                            "invoke_pass"
                                        ),
                                        class_register_num=local_count - 1,
                                    )
                                )
                                file_modified = True

                        # Encrypt the native libraries used in code and put them
                        # in assets folder.
                    if file_modified: #고도화 파일이 수정된 경우에만 암호화 수행  
                        self.logger.debug(f"Injecting decryption code into {smali_file}")
                     
                        assets_dir = obfuscation_info.get_assets_directory()
                        os.makedirs(assets_dir, exist_ok=True)
                        for native_lib in native_libs:
                            for lib_name in lib_names:
                                if native_lib.endswith("{0}.so".format(lib_name)):
                                    arch = os.path.basename(os.path.dirname(native_lib))
                                    encrypted_lib_path = os.path.join(
                                        assets_dir,
                                        "lib.{arch}.{lib_name}.so".format(
                                            arch=arch, lib_name=lib_name
                                        ),
                                    )
                                    #암호화 수행
                                    with open(native_lib, "rb") as native_lib_file:
                                        encrypted_lib = AES.new(
                                            key=self.encryption_secret.encode(),
                                            mode=AES.MODE_ECB,
                                        ).encrypt(
                                            pad(native_lib_file.read(), AES.block_size)
                                        )

                                    with open(
                                        encrypted_lib_path, "wb"
                                    ) as encrypted_lib_file:
                                        encrypted_lib_file.write(encrypted_lib)

                                    encrypted_to_original_mapping[
                                        encrypted_lib_path
                                    ] = native_lib

                    with open(smali_file, "w", encoding="utf-8") as current_file:
                        current_file.writelines(lines)

                if (
                    not obfuscation_info.decrypt_asset_smali_file_added_flag
                    and encrypted_to_original_mapping
                ):
                    # Add to the app the code for decrypting the encrypted native
                    # libraries. The code for decrypting can be put in any smali
                    # directory, since it will be moved to the correct directory
                    # when rebuilding the application.
                    destination_dir = os.path.dirname(
                        obfuscation_info.get_smali_files()[0]
                    )
                    destination_file = os.path.join(
                        destination_dir, "DecryptAsset.smali"
                    )
                    with open(
                        destination_file, "w", encoding="utf-8"
                    ) as decrypt_asset_smali:
                        decrypt_asset_smali.write(
                            util.get_decrypt_asset_smali_code(self.encryption_secret)
                        )
                        obfuscation_info.decrypt_asset_smali_file_added_flag = True

                # Remove the original native libraries that were encrypted (the
                # encrypted ones will be used instead).
                #원본 .so 파일 삭제
                for _, original_lib in encrypted_to_original_mapping.items():
                    try:
                        os.remove(original_lib)
                    except OSError as e:
                        self.logger.warning(
                            'Unable to delete native library "{0}": {1}'.format(
                                original_lib, e
                            )
                        )

            else:
                self.logger.debug("No native libraries found")

#고도화(예외처리 추가)
        except Exception as e:
            self.logger.error(
               self.logger.error(f'Error in LibEncryption: {e}')
                )
            raise PluginExecutionError(
                    plugin_name=self.__class__.__name__,
                    details=str(e)
                ) from e
            
           

        finally:
            obfuscation_info.used_obfuscators.append(self.__class__.__name__)
