from . import *

DEV = False
EXE = True

logger = Logger(dev=DEV, exe=EXE)

def get_current_dir():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(__file__)

    return application_path

class StellarisChecksumPatcher:
    def __init__(self) -> None:
        self.app_version = [0, 0, 6]
        self.hex_data_list = []
        self.__hex_data_list_working = []
        
        self.__dev = False
        
        self.data_loaded = False
        
        self.__chunk_char_len = 32 # Each line is comprised of 32 characters. Will need this to recompile from changed chunks back to binary
        
        self.__hex_begin_static = ['48', '8B', '12']
        self.__hex_end_static = ['85', 'C0']
        self.__hex_end_change_to = ['33', 'C0']
        self.__hex_wildcards_in_between = 14
        
        self.__checksum_block = []
        self.__checksum_offset_start = 0
        self.__checksum_offset_end = 0
        
        self.title_name = 'Stellaris'
        self.exe_default_filename = 'stellaris.exe'
        self.__exe_out_directory = os.path.dirname(sys.executable)
        self.__exe_modified_default_filename = 'stellaris-patched'
        
        self.__base_dir = os.path.dirname(sys.executable)
        
        self.__steam = steam_helper.SteamHelper()
        
        if self.__dev:
            self.__base_dir = os.path.abspath(os.path.join(get_current_dir(), os.pardir))
            self.__exe_out_directory = os.path.abspath(os.path.join(os.path.join(get_current_dir(), os.pardir), 'bin'))
            self.__exe_out_directory = os.path.abspath(os.path.join(get_current_dir(), os.pardir))
            pass
        
    def clear_caches(self):
        self.__hex_data_list_working.clear()
        self.__checksum_block.clear()
        self.__checksum_offset_start = 0
        self.__checksum_offset_end = 0
        
    def locate_game_install(self) -> os.path:
        logger.log('Locating game install...')
        stellaris_install_path = self.__steam.get_game_install_path(self.title_name)
        
        if stellaris_install_path:
            game_executable = os.path.join(stellaris_install_path, self.exe_default_filename)
            if not os.path.exists(game_executable):
                return None
            return game_executable
        
        return None
    
    def load_file_hex(self, file_path=None) -> bool:
        logger.log('Loading file Hex.')
        
        file_path = str(file_path).replace('/', '\\')
        
        if not file_path:
            file_path = os.path.join(self.__base_dir, self.exe_default_filename)
                
            if not os.path.isfile(file_path):
                logger.log_error(f'Unable to find required file: {file_path}')
                return False
        
        self.hex_data_list.clear()
        
        if not os.path.exists(file_path):
            logger.log_error(f'{file_path} does not exist.')
            return False
        
        with open(file_path, 'rb') as f:
            logger.log('Streaming File Hex Info...')
            while True:
                hex_data = f.read(16).hex()
                if len(hex_data) == 0:
                    break
                self.hex_data_list.append(hex_data.upper())
        
        self.hex_data = ''.join(self.hex_data_list)
        self.data_loaded = True
        logger.log('Read Finished.')
        
        return True
    
    def _generate_missing_paths(self, dir_path) -> None:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    
    def write_hex_to_file(self, directory, filename, working_set=False):
        dest = os.path.join(directory, f'{filename}.txt')
        
        self._generate_missing_paths(directory)
        
        to_write = self.hex_data_list
        
        if working_set:
            to_write = self.__hex_data_list_working
        
        with open(dest, 'w') as f:
            for chunk in to_write:
                f.write(chunk+'\n')
    
    def compile_hex_file(self, directory=None, filename=None):
        if not directory:
            directory = self.__exe_out_directory
        
        if not filename:
            filename = self.__exe_modified_default_filename
            
        dest = os.path.join(directory, f'{filename}.exe')
        
        if directory:
            self._generate_missing_paths(directory)
        else:
            self._generate_missing_paths()
            
        with open(dest, 'wb') as out:
            for line in self.__hex_data_list_working:
                chunk = binascii.unhexlify(str(line).rstrip())
                out.write(chunk)
            if EXE:
                logger.log(f'Writing {filename}.exe to: {directory}')
            else:
                logger.log(f'Writing {Colours.YELLOW}{filename}.exe{Colours.DEFAULT} to: {directory}')
            
        return True
            
    def __convert_to_two_space(self, condense_chunks=False) -> list:
        # https://stackoverflow.com/a/10070449
        
        # Convert current loaded hex to two space, so from 'XXXXXXXX' to ['XX', 'XX', 'XX', 'XX',..]
        
        logger.log_debug('Formatting hexadecimal data to working set...')
        
        formatted_hex_data_list = []
        
        for chunk in self.hex_data_list:
            converted = ' '.join(chunk[i:i+2] for i in range(0,len(chunk),2))
            formatted_hex_data_list.append(converted)
            
        if condense_chunks:
            logger.log_debug('Condensing chunks...') # Here we take the list of chunks [['XX', 'XX', 'XX',..], ['XX', 'XX', 'XX', 'XX',..]] and turn all into a single chunk -> ["XX, XX, XX, XX, XX,.."]
            self.__hex_data_list_working.append(' '.join(formatted_hex_data_list))
        else:
            self.__hex_data_list_working = formatted_hex_data_list
        
        return self.__hex_data_list_working
    
    def convert_hex_list_to_writable_chunk_list(self, hex_chunk_set: list) -> list:
        out_list = []
        
        tmp_chunk = []
        iter = 0
        for hex_char in hex_chunk_set:
            if iter < (self.__chunk_char_len)/2:
                tmp_chunk.append(hex_char)
            else:
                out_list.append(''.join(tmp_chunk))
                tmp_chunk.clear()
                iter = 0
                tmp_chunk .append(hex_char)
                
            iter += 1
        
        return out_list
            
    def acquire_checksum_block(self) -> bool:
        logger.log('Acquiring Checksum Block...')
        
        working_set_hex = self.__convert_to_two_space(condense_chunks=True)
        
        potential_candidate = False
        
        for chunk in working_set_hex:
            chunk_split = chunk.split(' ')
            for index, hex_char in enumerate(chunk_split):
                # CHECK FOR START SEQUENCE
                if hex_char in self.__hex_begin_static and hex_char == self.__hex_begin_static[0]:
                    # logger.log_debug(f'Found matching starting hex <{hex_char}> at index {index}')
                    start_candidate = []
                    start_sequence_len = len(self.__hex_begin_static)
                    
                    for i in range(start_sequence_len):
                        start_candidate.append(chunk_split[index+i])
                    if start_candidate == self.__hex_begin_static:
                        # logger.log_debug(f'Found potential start candidate: {start_candidate} starting from {index}')
                        
                        # CHECK FOR END SEQUENCE AFTER X WILDCARDS IN BETWEEN
                        # logger.log_debug('Checking for end sequence')
                        end_sequence_candidate = []
                        end_sequence_len = len(self.__hex_end_static)
                        
                        # [start_index_chars, start_index_chars+1, start_index_chars+2, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, 16??, end_hex_char, end_hex_char+1]
                        # [48, 8B, 12, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, ??, 85, C0]
                        search_offset_start = index + start_sequence_len + self.__hex_wildcards_in_between
                        # logger.log_debug(f'Search Offset Start {search_offset_start}')
                        for end_candidate in chunk_split[search_offset_start:search_offset_start + end_sequence_len]:
                            end_sequence_candidate.append(end_candidate)
                        
                        # logger.log_debug(f'End Candidate: {end_sequence_candidate}')
                        
                        if end_sequence_candidate == self.__hex_end_static:
                            # logger.log_debug(f'Found potential start candidate: {start_candidate} starting from {index}')
                            # logger.log_debug(f'Found potential end candidate: {end_sequence_candidate} ending at index {search_offset_start + end_sequence_len}')
                            # logger.log_debug(f'Search Offset Start: {search_offset_start-index}')
                            self.__checksum_block = [hex_chunk for hex_chunk in chunk_split[index:search_offset_start + end_sequence_len]]
                            self.__checksum_offset_start = index
                            self.__checksum_offset_end = search_offset_start + end_sequence_len
                            logger.log(f'Found potential matching sequence.')
                            logger.log_debug(f'({index}) {"".join(self.__checksum_block)} ({search_offset_start + self.__checksum_offset_end})')
                            potential_candidate = True
                            break
        
        if potential_candidate:
            return True
        
        return False

    def modify_checksum(self):
        logger.log('Patching Block...')
        if not self.__checksum_block:
            return False
        
        checksum_block_modified = []
        for enum, hex_char in enumerate(self.__checksum_block):
            if enum >= len(self.__checksum_block) - len(self.__hex_end_change_to):
                checksum_block_modified.extend(self.__hex_end_change_to)
                break
            else:
                checksum_block_modified.append(hex_char)
                
        logger.log_debug(f'Original Block:  {"".join(self.__checksum_block)}')            
        logger.log_debug(f'Modified Block: {"".join(checksum_block_modified)}')

        if not self.__hex_data_list_working:
            return False
        
        for chunk in self.__hex_data_list_working:
            chunk_split = chunk.split(' ')
            for offset, modify_hex in enumerate(checksum_block_modified):
                chunk_split[self.__checksum_offset_start+offset] = modify_hex
    
        self.__hex_data_list_working = self.convert_hex_list_to_writable_chunk_list(chunk_split)
        
        return True
        
    def patch(self) -> None:
        self.clear_caches()
        
        if not self.data_loaded:
            op_success = False
        else:
            op_success = True
        
        if op_success:
            op_success = self.acquire_checksum_block()
            
            if op_success:
                op_success = self.modify_checksum()
            
            if op_success:
                op_success = self.compile_hex_file()
        
        if op_success:
            print('\n')
            if EXE:
                logger.log(f'Patch successful.')
            else:
                logger.log(f'Patch {Colours.GREEN}successful{Colours.DEFAULT}.')
            return True
        else:
            print('\n')
            if EXE:
                logger.log(f'Patch failed.')
            else:
                logger.log(f'Patch {Colours.RED}failed{Colours.DEFAULT}.')
    
        return False
        
    